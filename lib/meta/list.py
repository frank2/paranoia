#!/usr/bin/env python

from paranoia.base import declaration, memory_region, size_hint, paranoia_agent
from paranoia.converters import *

try:
    import __builtin__
except ImportError: # python3
    import builtins as __builtin__

__all__ = ['is_size_hint', 'ListError', 'List']

def is_size_hint(decl):
    return issubclass(decl.base_class, size_hint.SizeHint)

class ListError(paranoia_agent.ParanoiaError):
    pass

class List(memory_region.MemoryRegion):
    DECLARATIONS = None
    BIND = True
    COPY_DECLARATIONS = True

    def __init__(self, **kwargs):
        # yank necessary MemoryRegion args from the kwargs
        self.allocation = kwargs.setdefault('allocation', self.ALLOCATION)
        self.alignment = kwargs.setdefault('alignment', self.ALIGNMENT)
        self.bitshift = kwargs.setdefault('bitshift', self.BITSHIFT)
        self.parent_region = kwargs.setdefault('parent_region', self.PARENT_REGION)
        self.copy_declarations = kwargs.setdefault('copy_declarations', self.COPY_DECLARATIONS)
        self.bind = kwargs.setdefault('bind', self.BIND)        
        self.declarations = kwargs.setdefault('declarations', self.DECLARATIONS)

        if self.declarations is None:
            self.declarations = list()

        if not isinstance(self.declarations, list):
            raise ListError('declarations must be a list of Declaration objects')

        self.map_declarations()

        self.recalculating = False
        self.declaration_offsets = dict()
        self.previous_offsets = dict()
        self.deltas = dict()
        self.hint_map = dict()
        self.instance_map = dict()
        
        if 'string_data' in kwargs and not kwargs['string_data'] is None:
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

    def map_declarations(self):
        self.declaration_map = dict()
        
        for i in range(len(self.declarations)):
            decl_obj = self.declarations[i]

            if not isinstance(decl_obj, declaration.Declaration):
                raise ListError('declaration object is not a Declaration')

            if self.copy_declarations:
                decl_obj = decl_obj.copy()
                self.declarations[i] = decl_obj

            decl_hash = hash(decl_obj)
            self.declaration_map[decl_hash] = decl_obj

    def map_hint(self, index):
        declaration_obj = self.declarations[index]
        declaration_hash = hash(declaration_obj)

        if not is_size_hint(declaration_obj):
            raise ListError('map_hint argument not a size hint')

        resolved_decl = declaration_obj.get_arg('resolved_declaration')
        target_decl = declaration_obj.get_arg('target_declaration')

        if not resolved_decl is None:
            if resolved_decl not in self.declaration_map:
                raise ListError('no such declaration with hash %x', resolved_decl)
        else:
            if target_decl is None:
                raise ListError('size hint has no target declaration')

            if isinstance(target_decl, str):
                raise ListError('list cannot resolve strings')

            if target_decl >= len(self.declarations):
                raise ListError('target_index out of bounds')

            resolved_decl = hash(self.declarations[target_decl])
                    
        self.hint_map[resolved_decl] = declaration_hash

    def calculate_offsets(self, start_from=0):
        long = getattr(__builtin__, 'long', None)

        if long is None: # python 3
            long = int
            
        if isinstance(start_from, declaration.Declaration):
            start_from = self.declarations.index(start_from)
        elif not isinstance(start_from, (int, long)):
            raise ListError('start_from must be an int, long or Declaration')
            
        declarative_length = len(self.declarations)
        self.previous_offsets = dict(list(self.declaration_offsets.items())[:])
        self.hint_map = dict([x for x in list(self.hint_map.items()) if x[0] < declarative_length])

        memory_base = getattr(self, 'memory_base', None)

        for i in range(start_from, len(self.declarations)):
            declaration_obj = self.declarations[i]
            declaration_hash = hash(declaration_obj)

            if is_size_hint(declaration_obj):
                self.map_hint(i)
            elif not memory_base is None and declaration_hash in self.hint_map:
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

                new_memory_offset = previous_memory_offset + int(shift_and_span / 8)
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
        elif not isinstance(start_from, int):
            raise ListError('start_from must be an int, long or Declaration')

        for i in range(len(self.declarations)):
            decl = self.declarations[i]
            decl_hash = hash(decl)

            if decl_hash not in self.previous_offsets:
                continue

            current = self.declaration_offsets[decl_hash]
            previous = self.previous_offsets[decl_hash]

            current_pos = current['memory_offset'] * 8 + current['bitshift']
            previous_pos = previous['memory_offset'] * 8 + previous['bitshift']

            self.deltas[decl_hash] = current_pos - previous_pos

    def calculate_length(self):
        list_bitspan = 0
        
        for i in range(len(self.declarations)):
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
        
        for i in range(len(self.declarations)):
            decl = self.declarations[i]
            decl_hash = hash(decl)

            if decl_hash not in self.deltas:
                continue

            if self.deltas[decl_hash] >= 0:
                continue
            
            previous = self.previous_offsets[decl_hash]
            previous_pos = previous['memory_offset'] * 8 + previous['bitshift']
            delta_pos = previous_pos + self.deltas[decl_hash]

            self.move_bits(delta_pos, previous_pos, previous['bitspan'])

            if decl_hash not in self.instance_map:
                continue
            
            instance = self.instance_map[decl_hash]
            offsets = self.declaration_offsets[decl_hash]
                    
            instance.memory_base = self.memory_base.fork(offsets['memory_offset'])
            instance.bitshift = offsets['bitshift']

            if isinstance(instance, List):
                instance.reset_instances()

    def move_positive_deltas(self):
        memory_base = getattr(self, 'memory_base', None)

        if memory_base is None:
            return
        
        for i in range(len(self.declarations))[::-1]:
            decl = self.declarations[i]
            decl_hash = hash(decl)

            if decl_hash not in self.deltas:
                continue
            
            if self.deltas[decl_hash] <= 0:
                continue
            
            previous = self.previous_offsets[decl_hash]
            previous_pos = previous['memory_offset'] * 8 + previous['bitshift']
            delta_pos = previous_pos + self.deltas[decl_hash]
            
            self.move_bits(delta_pos, previous_pos, previous['bitspan'])
            
            if decl_hash not in self.instance_map:
                continue
            
            instance = self.instance_map[decl_hash]
            current = self.declaration_offsets[decl_hash]
                    
            instance.memory_base = self.memory_base.fork(current['memory_offset'])
            instance.bitshift = current['bitshift']

            if isinstance(instance, List):
                instance.reset_instances()
                
    def recalculate(self, start_from=0):
        # this prevents recursion loops in instantiated size hints
        if self.recalculating:
            return

        self.recalculating = True
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

        self.recalculating = False

    def reset_instances(self):
        for decl_hash in list(self.instance_map.keys()):
            instance = self.instance_map[decl_hash]
            offsets = self.declaration_offsets[decl_hash]

            instance.memory_base = self.memory_base.fork(offsets['memory_offset'])
            instance.bitshift = offsets['bitshift']

            if isinstance(instance, List):
                instance.reset_instances()
            
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
                if resolved_decl not in self.hint_map:
                    raise ListError('no such hint with hash %x' % resolved_decl)
            else:
                if target_decl is None:
                    raise ListError('size hint has no target')

                if isinstance(target_decl, str):
                    raise ListError('list cannot resolve strings')

                if target_decl >= len(self.declarations):
                    raise ListError('target index out of bounds')

                resolved_decl = hash(self.declarations[target_decl])
                
            del self.hint_map[resolved_decl]

        if declaration_hash in self.instance_map:
            del self.instance_map[declaration_hash]

        if skip_recalc:
            return

        if index == 0:
            self.recalculate()
        else:
            self.recalculate(index-1)

    def instantiate(self, index):
        if index in self.declaration_map:
            decl_hash = index
        else:
            if abs(index) >= len(self.declarations):
                raise ListError('index out of range')

            if index < 0:
                index += len(self.declarations)

            decl_hash = hash(self.declarations[index])

        if decl_hash in self.instance_map:
            return self.instance_map[decl_hash]

        if decl_hash not in self.declaration_offsets:
            raise ListError('offset for declaration not parsed')
        
        memory_base = self.memory_base.fork(self.declaration_offsets[decl_hash]['memory_offset'])
        bitshift = self.declaration_offsets[decl_hash]['bitshift']

        instance = self.declaration_map[decl_hash].instantiate(memory_base=memory_base
                                                               ,bitshift=bitshift
                                                               ,parent_region=self)

        self.instance_map[decl_hash] = instance

        return instance

    def read_memory(self):
        # initialize all the arguments to get the most accurate read-out of
        # what should be in the object
        for i in range(len(self.declarations)):
            self.instantiate(i)

        return super(List, self).read_memory()

    def __getitem__(self, index):
        return self.instantiate(index)
    
    @classmethod
    def static_bitspan(cls, **kwargs):
        declarations = kwargs.setdefault('declarations', cls.DECLARATIONS)
        
        if declarations is None:
            raise ListError('no static declarations to parse bitspan from')

        memory_base = kwargs.setdefault('memory_base', cls.MEMORY_BASE)
        bitshift = kwargs.setdefault('bitshift', cls.BITSHIFT)
        bitspan = 0
        memory_offset = 0

        declaration_offsets = dict()
        hint_map = dict()

        for i in range(len(declarations)):
            declaration = declarations[i]

            if not memory_base is None and i in hint_map:
                hint_dict = hint_map[i]
                hint_declaration = declarations[hint_dict['index']]
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
                new_memory_base = memory_base.fork(offset_dict['memory_offset'])
                new_bitspan = declaration.bitspan(memory_base=new_memory_base)
            else:
                new_bitspan = declaration.bitspan()

            offset_dict['bitspan'] = new_bitspan
            
            bitspan += new_bitspan

            if not memory_base is None and is_size_hint(declaration):
                hint_dict = {'memory_base': memory_base.fork(offset_dict['memory_offset'])
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
