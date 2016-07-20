#!/usr/bin/env python

from paranoia.base import declaration, memory_region, size_hint, paranoia_agent
from paranoia.converters import *

def is_size_hint(decl):
    return issubclass(decl.base_class, size_hint.SizeHint)

class ListError(paranoia_agent.ParanoiaError):
    pass

class List(memory_region.MemoryRegion):
    BIND = True
    DECLARATIONS = None

    def __init__(self, **kwargs):
        # yank necessary MemoryRegion args from the kwargs
        self.allocation = kwargs.setdefault('allocation', self.ALLOCATION)
        self.alignment = kwargs.setdefault('alignment', self.ALIGNMENT)
        self.bitshift = kwargs.setdefault('bitshift', self.BITSHIFT)
        self.parent_region = kwargs.setdefault('parent_region', self.PARENT_REGION)

        self.bind = kwargs.setdefault('bind', self.BIND)
        self.declarations = kwargs.setdefault('declarations', self.DECLARATIONS)

        if self.declarations is None:
            self.declarations = list()

        if not isinstance(self.declarations, list):
            raise ListError('declarations must be a list of Declaration objects')

        self.declaration_map = dict()
        
        for i in xrange(len(self.declarations)):
            declaration_obj = self.declarations[i]

            if not isinstance(declaration_obj, declaration.Declaration):
                raise ListError('declaration at offset %d is not a Declaration object' % i)

            self.declaration_map[hash(declaration_obj)] = declaration_obj

        self.declaration_offsets = dict()
        self.previous_offsets = dict()
        self.deltas = dict()
        self.hint_map = dict()
        
        if kwargs.has_key('string_data') and not kwargs['string_data'] is None:
            # if string data is present, use that as the length and calculate
            # offsets with memory hints afterward
            kwargs['bitspan'] = len(kwargs['string_data'])*8
        else:
            # otherwise, calculate the offsets without memory hints
            self.recalculate()
            kwargs['bitspan'] = self.bitspan

        memory_region.MemoryRegion.__init__(self, **kwargs)

        # recalculate and reallocate
        self.recalculate()

    def map_hint(self, index):
        declaration_obj = self.declarations[index]
        declaration_hash = hash(declaration_obj)

        if not is_size_hint(declaration_obj):
            raise ListError('map_hint argument not a size hint')

        resolved_decl = declaration_obj.get_arg('resolved_declaration')
        target_decl = declaration_obj.get_arg('target_declaration')

        if not resolved_decl is None:
            if not self.declaration_map.has_key(resolved_decl):
                raise ListError('no such declaration with hash %x', resolved_decl)
        else:
            if target_decl is None:
                raise ListError('size hint has no target declaration')

            if isinstance(target_decl, basestring):
                raise ListError('list cannot resolve strings')

            if target_decl >= len(self.declarations):
                raise ListError('target_index out of bounds')

            resolved_decl = hash(self.declarations[target_decl])
                    
        self.hint_map[resolved_decl] = declaration_hash

    def calculate_offsets(self, start_from=0):
        if isinstance(start_from, declaration.Declaration):
            start_from = self.declarations.index(start_from)
        elif not isinstance(start_from, (int, long)):
            raise ListError('start_from must be an int, long or Declaration')
            
        declarative_length = len(self.declarations)
        self.previous_offsets = dict(self.declaration_offsets.items()[:])
        self.hint_map = dict(filter(
            lambda x: x[0] < declarative_length
            ,self.hint_map.items()))

        memory_base = getattr(self, 'memory_base', None)

        for i in range(start_from, len(self.declarations)):
            declaration_obj = self.declarations[i]
            declaration_hash = hash(declaration_obj)

            if is_size_hint(declaration_obj):
                self.map_hint(i)
            elif not memory_base is None and self.hint_map.has_key(declaration_hash):
                hint_hash = self.hint_map[declaration_hash]
                hint_object = self.instantiate(hint_hash)
                hint_object.set_declaration()

            offset_dict = dict()
            alignment = declaration_obj.alignment()

            if i == 0:
                offset_dict['memory_offset'] = 0
                offset_dict['bitshift'] = self.bitshift
            else:
                previous_decl = self.declarations[i-1]
                previous_hash = hash(previous_decl)
                previous_offset = self.declaration_offsets[previous_hash]
                previous_shift = previous_offset['bitshift']
                previous_span = previous_offset['bitspan']
                previous_memory_offset = previous_offset['memory_offset']

                shift_and_span = align(previous_shift + previous_span, alignment)

                new_memory_offset = previous_memory_offset + (shift_and_span / 8)
                new_shift = shift_and_span % 8
                
                offset_dict['bitshift'] = new_shift
                offset_dict['memory_offset'] = new_memory_offset

            if not memory_base is None:
                new_memory_base = memory_base.fork(offset_dict['memory_offset'])
                bitspan = declaration_obj.bitspan(memory_base=new_memory_base)
            else:
                bitspan = declaration_obj.bitspan()

            offset_dict['bitspan'] = bitspan

            self.declaration_offsets[declaration_hash] = offset_dict

    def calculate_deltas(self, start_from=0):
        if isinstance(start_from, declaration.Declaration):
            start_from = self.declarations.index(start_from)
        elif not isinstance(start_from, (int, long)):
            raise ListError('start_from must be an int, long or Declaration')

        for i in xrange(len(self.declarations)):
            decl = self.declarations[i]
            decl_hash = hash(decl)

            if not self.previous_offsets.has_key(decl_hash):
                continue

            current = self.declaration_offsets[decl_hash]
            previous = self.previous_offsets[decl_hash]

            current_pos = current['memory_offset'] * 8 + current['bitshift']
            previous_pos = previous['memory_offset'] * 8 + previous['bitshift']

            self.deltas[decl_hash] = current_pos - previous_pos

    def calculate_length(self):
        list_bitspan = 0
        
        for i in xrange(len(self.declarations)):
            current = self.declaration_offsets[hash(self.declarations[i])]

            if i+1 >= len(self.declarations):
                next_decl = None
            else:
                next_decl = self.declaration_offsets[hash(self.declarations[i+1])]

            if next_decl is None:
                list_bitspan += current['bitspan']
            else:
                current_bitpos = current['memory_offset'] * 8 + current['bitshift']
                next_bitpos = next_decl['memory_offset'] * 8 + next_decl['bitshift']
                list_bitspan += next_bitpos - current_bitpos

        self.bitspan = list_bitspan

    def move_negative_deltas(self):
        memory_base = getattr(self, 'memory_base', None)

        if memory_base is None:
            return
        
        for i in xrange(len(self.declarations)):
            decl = self.declarations[i]
            decl_hash = hash(decl)

            if not self.deltas.has_key(decl_hash):
                continue

            if self.deltas[decl_hash] < 0:
                previous = self.previous_offsets[decl_hash]
                previous_pos = previous['memory_offset'] * 8 + previous['bitshift']
                delta_pos = previous_pos + self.deltas[decl_hash]

                self.move_bits(delta_pos, previous_pos, previous['bitspan'])

    def move_positive_deltas(self):
        memory_base = getattr(self, 'memory_base', None)

        if memory_base is None:
            return
        
        for i in range(len(self.declarations))[::-1]:
            decl = self.declarations[i]
            decl_hash = hash(decl)

            if not self.deltas.has_key(decl_hash):
                continue
            
            if self.deltas[decl_hash] > 0:
                previous = self.previous_offsets[decl_hash]
                previous_pos = previous['memory_offset'] * 8 + previous['bitshift']
                delta_pos = previous_pos + self.deltas[decl_hash]

                import ctypes
                
                self.move_bits(delta_pos, previous_pos, previous['bitspan'])
                
    def recalculate(self, start_from=0):
        self.calculate_offsets(start_from)
        self.calculate_deltas()

        self.move_negative_deltas()

        self.calculate_length()

        parent_region = getattr(self, 'parent_region', None)
        root_declaration = getattr(self, 'declaration', None)

        if not parent_region is None and isinstance(parent_region, List) and not root_declaration is None and root_declaration in parent_region.declarations:
            parent_region.recalculate(root_declaration)
        
        self.reallocate()

        self.move_positive_deltas()

    def append_declaration(self, declaration, skip_recalc=False):
        self.insert_declaration(len(self.declarations), declaration, skip_recalc)

    def append_declarations(self, declarations, skip_recalc=False):
        start_from = len(self.declarations)
        
        for declaration in declarations:
            self.append_declaration(declaration, True)

        if skip_recalc:
            return

        self.recalculate(start_from)

    def insert_declaration(self, index, declaration_obj, skip_recalc=False):
        if self.bind and not self.is_allocated():
            raise ListError('cannot dynamically modify declarations without allocation')
        
        if abs(index) > len(self.declarations):
            raise ListError('index out of range')

        if not isinstance(declaration_obj, declaration.Declaration):
            raise ListError('declaration must implement DataDeclaration')

        # even though negative indexes can insert just fine with python lists, we
        # adjust the negative index for the call to calculate_offsets.
        if index < 0:
            index += len(self.declarations)

        self.declarations.insert(index, declaration_obj)
        self.declaration_map[hash(declaration_obj)] = declaration_obj

        if skip_recalc:
            return
        
        self.recalculate(index)

    def remove_declaration(self, index, skip_recalc=False):
        if self.bind and not self.is_allocated():
            raise ListError('cannot dynamically modify declarations without allocation')
        
        if abs(index) > len(self.declarations):
            raise DataListError('index out of range')

        # even though negative indexes can remove just fine with python lists, we
        # adjust the negative index for the call to calculate_offsets.
        if index < 0:
            index += len(self.declarations)

        declaration_obj = self.declarations.pop(index)
        declaration_hash = hash(declaration_obj)
        del self.declaration_map[declaration_hash]
        del self.declaration_offsets[declaration_hash]

        if is_size_hint(declaration_obj):
            resolved_decl = declaration_obj.get_arg('resolved_declaration')
            target_decl = declaration_obj.get_arg('target_declaration')

            if not resolved_decl is None:
                if not self.hint_map.has_key(resolved_decl):
                    raise ListError('no such hint with hash %x' % resolved_decl)
            else:
                if target_decl is None:
                    raise ListError('size hint has no target')

                if isinstance(target_decl, basestring):
                    raise ListError('list cannot resolve strings')

                if target_decl >= len(self.declarations):
                    raise ListError('target index out of bounds')

                resolved_decl = hash(self.declarations[target_decl])
                
            del self.hint_map[resolved_decl]

        if skip_recalc:
            return

        if index == 0:
            self.recalculate()
        else:
            self.recalculate(index-1)

    def instantiate(self, index):
        if self.declaration_map.has_key(index):
            decl_hash = index
        else:
            if abs(index) > len(self.declarations):
                raise ListError('index out of range')

            if index < 0:
                index += len(self.declarations)

            decl_hash = hash(self.declarations[index])

        if not self.declaration_offsets.has_key(decl_hash):
            raise ListError('offset for declaration not parsed')
        
        memory_base = self.memory_base.fork(self.declaration_offsets[decl_hash]['memory_offset'])
        bitshift = self.declaration_offsets[decl_hash]['bitshift']

        instance = self.declaration_map[decl_hash].instantiate(memory_base=memory_base
                                                               ,bitshift=bitshift
                                                               ,parent_region=self)

        return instance

    def read_memory(self):
        bitlist = list()

        for i in xrange(len(self.declarations)):
            instance = self.instantiate(i)
            bitlist += instance.read_bits(instance.bitspan)

        return ''.join(map(chr, bitlist_to_bytelist(bitlist)))

    def __getitem__(self, index):
        return self.instantiate(index)
    
    @classmethod
    def static_bitspan(cls, **kwargs):
        if not cls.DECLARATIONS:
            raise ListError('no static declarations to parse bitspan from')

        memory_base = kwargs.setdefault('memory_base', cls.MEMORY_BASE)
        bitshift = kwargs.setdefault('bitshift', cls.BITSHIFT)
        bitspan = 0
        memory_offset = 0

        declaration_offsets = dict()
        hint_map = dict()

        for i in xrange(len(cls.DECLARATIONS)):
            declaration = cls.DECLARATIONS[i]

            if not memory_base is None and hint_map.has_key(i):
                hint_dict = hint_map[i]
                hint_declaration = cls.DECLARATIONS[hint_dict['index']]
                del hint_dict['index']
                hint_instance = hint_declaration.instantiate(**hint_dict)
                declaration.set_arg(hint_instance.argument, hint_instance.get_value())

            offset_dict = dict()
            alignment = declaration.alignment()
            
            if i == 0:
                offset_dict['memory_offset'] = 0
                offset_dict['bitshift'] = bitshift
            else:
                previous_offset = declaration_offsets[i-1]
                previous_shift = previous_offset['bitshift']
                previous_span = previous_offset['bitspan']
                previous_memory_offset = previous_offset['memory_offset']

                shift_and_span = align(previous_shift + previous_span, alignment)

                new_memory_offset = previous_memory_offset + (shift_and_span / 8)
                new_shift = shift_and_span % 8

                ofset_dict['bitshift'] = new_shift
                offset_dict['memory_offset'] = new_memory_offset

            if not memory_base is None:
                new_memory_base = offset_dict['memory_offset'] + memory_base
                new_bitspan = declaration.bitspan(memory_base=new_memory_base)
            else:
                new_bitspan = declaration.bitspan()

            offset_dict['bitspan'] = new_bitspan
            
            bitspan += new_bitspan

            if not memory_base is None and declaration.is_size_hint():
                hint_dict = {'memory_base': memory_base+offset_dict['memory_offset']
                             ,'bitshift': offset_dict['bitshift']
                             ,'index': i}
                hint_map[declaration.get_arg('target_declaration')] = hint_dict

        return bitspan

    @classmethod
    def static_declaration(cls, **kwargs):
        kwargs.setdefault('declarations', cls.DECLARATIONS)

        super_class = super(List, cls).static_declaration(**kwargs)

        class StaticList(super_class):
            DECLARATIONS = kwargs['declarations']

        return StaticList
