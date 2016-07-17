#!/usr/bin/env python

from paranoia.base import declaration, memory_region, size_hint, paranoia_agent
from paranoia.converters import *

def is_size_hint(decl):
    return issubclass(decl.base_class, size_hint.SizeHint)

class ListError(paranoia_agent.ParanoiaError):
    pass

class List(memory_region.MemoryRegion):
    DECLARATIONS = None

    def __init__(self, **kwargs):
        # yank MemoryRegion's bitshift arg from the kwargs
        self.bitshift = kwargs.setdefault('bitshift', self.BITSHIFT)
        self.declarations = kwargs.setdefault('declarations', self.DECLARATIONS)

        if self.declarations is None:
            self.declarations = list()

        if not isinstance(self.declarations, list):
            raise ListError('declarations must be a list of Declaration objects')

        for i in xrange(len(self.declarations)):
            declaration_obj = self.declarations[i]

            if not isinstance(declaration_obj, declaration.Declaration):
                raise ListError('declaration at offset %d is not a Declaration object' % i)

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
            self.calculate_offsets()
            kwargs['bitspan'] = self.bitspan

        memory_region.MemoryRegion.__init__(self, **kwargs)

        # recalculate and reallocate
        self.calculate_offsets()

    def map_hint(self, index):
        declaration_obj = self.declarations[index]

        if not is_size_hint(declaration_obj):
            raise ListError('map_hint argument not a size hint')

        declaration_obj.set_arg('my_declaration', index)
        target_index = declaration_obj.get_arg('target_declaration')

        if target_index is None:
            raise ListError('size hint has no target declaration')

        self.hint_map[target_index] = index

    def calculate_offsets(self, start_from=0):
        if isinstance(start_from, declaration.Declaration):
            start_from = self.declarations.index(start_from)
        elif not isinstance(start_from, (int, long)):
            raise ListError('start_from must be an int, long or Declaration')
            
        # truncate the declaration offsets to only that which currently exist
        declarative_length = len(self.declarations)
        self.previous_offsets = dict(self.declaration_offsets.items()[:])
        self.declaration_offsets = dict(filter(lambda x: x[0] < declarative_length, self.declaration_offsets.items()))
        self.hint_map = dict(filter(lambda x: x[0] < declarative_length, self.hint_map.items()))

        old_bitspan = getattr(self, 'bitspan', None)
        memory_base = getattr(self, 'memory_base', None)
        parent_region = getattr(self, 'parent_region', None)
        root_declaration = getattr(self, 'declaration', None)

        if start_from > 0:
            list_bitspan = sum(map(lambda x: self.declaration_offsets[x]['bitspan'], range(0, start_from)))
        else:
            list_bitspan = 0

        for i in range(start_from, len(self.declarations)):
            declaration_obj = self.declarations[i]

            if is_size_hint(declaration_obj):
                self.map_hint(i)
            elif not memory_base is None and self.hint_map.has_key(i):
                hint_index = self.hint_map[i]
                hint_object = self.instantiate(hint_index)
                hint_value = hint_object.get_value()

                declaration_obj.args[hint_object.argument] = hint_value

            offset_dict = dict()
            alignment = declaration_obj.alignment()

            if i == 0:
                offset_dict['memory_offset'] = 0
                offset_dict['bitshift'] = self.bitshift
            else:
                previous_offset = self.declaration_offsets[i-1]
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
                
            list_bitspan += bitspan
            offset_dict['bitspan'] = bitspan

            self.declaration_offsets[i] = offset_dict
            
        self.bitspan = list_bitspan

        if parent_region and isinstance(parent_region, List) and root_declaration and root_declaration in parent_region.declarations:
            parent_region.calculate_offsets(root_declaration)
            
        if not old_bitspan is None and not old_bitspan == self.bitspan and self.is_allocated():
            self.reallocate()

    def append_declaration(self, declaration):
        self.insert_declaration(len(self.declarations), declaration)

    def insert_declaration(self, index, declaration_obj):
        if abs(index) > len(self.declarations):
            raise ListError('index out of range')

        if not isinstance(declaration_obj, declaration.Declaration):
            raise ListError('declaration must implement DataDeclaration')

        # even though negative indexes can insert just fine with python lists, we
        # adjust the negative index for the call to calculate_offsets.
        if index < 0:
            index += len(self.declarations)

        self.declarations.insert(index, declaration_obj)
        self.calculate_offsets(index)

    def remove_declaration(self, index):
        if abs(index) > len(self.declarations):
            raise DataListError('index out of range')

        # even though negative indexes can remove just fine with python lists, we
        # adjust the negative index for the call to calculate_offsets.
        if index < 0:
            index += len(self.declarations)

        declaration_obj = self.declarations.pop(index)

        if is_size_hint(declaration_obj):
            del self.hint_map[declaration_obj.get_arg('target_declaration')]

        if index == 0:
            self.calculate_offsets()
        else:
            self.calculate_offsets(index-1)

    def instantiate(self, index):
        if abs(index) > len(self.declarations):
            raise ListError('index out of range')

        if index < 0:
            index += len(self.declarations)

        if not self.declaration_offsets.has_key(index):
            raise ListError('offset for index not parsed')

        print '[instantiate] self.memory_base =', hex(int(self.memory_base))
        print '[instantiate] memory_offset =', self.declaration_offsets[index]['memory_offset']

        memory_base = self.memory_base.fork(self.declaration_offsets[index]['memory_offset'])
        bitshift = self.declaration_offsets[index]['bitshift']

        instance = self.declarations[index].instantiate(memory_base=memory_base
                                                        ,bitshift=bitshift
                                                        ,parent_region=self)

        return instance

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
                declaration.args[hint_instance.argument] = hint_instance.get_value()

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
                hint_map[declaration.target_declaration()] = hint_dict

        return bitspan

    @classmethod
    def static_declaration(cls, **kwargs):
        kwargs.setdefault('declarations', cls.DECLARATIONS)

        super_class = super(List, cls).static_declaration(**kwargs)

        class StaticList(super_class):
            DECLARATIONS = kwargs['declarations']

        return StaticList
