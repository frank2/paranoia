#!/usr/bin/env python

from .. import memory_region, size_hint, paranoia_agent
from ..abstract import declaration
from paranoia.converters import *

class ListError(paranoia_agent.ParanoiaError):
    pass

class List(memory_region.MemoryRegion):
    DECLARATIONS = None

    def __init__(self, **kwargs):
        self.declarations = kwargs.setdefault('declarations', self.DECLARATIONS)

        if self.declarations is None:
            self.declarations = list()

        if not isinstance(self.declarations, list):
            raise ListError('declarations must be a list of Declaration objects')

        self.memory_base = kwargs.setdefault('memory_base', self.MEMORY_BASE)
        self.bitshift = kwargs.setdefault('bitshift', self.BITSHIFT)

        self.declaration_offsets = dict()
        self.hint_map = dict()
                
        #was_none = self.memory_base == None

        #if was_none:
        #    self.memory_base = 0
            
        self.calculate_offsets()

        #if was_none:
        #    self.memory_base = None

        kwargs['bitspan'] = self.bitspan

        memory_region.MemoryRegion.__init__(self, **kwargs)

        #if was_none:
        #    for k in self.declaration_offsets.keys():
        #        self.declaration_offsets[k]['memory_base'] += self.memory_base

    def map_hint(self, index):
        declaration = self.declarations[index]

        if not declaration.is_size_hint():
            raise ListError('map_hint argument not a size hint')

        declaration.args['my_declaration'] = index
        target_index = declaration.target_declaration()

        if target_index is None:
            raise ListError('size hint has no target declaration')

        self.hint_map[target_index] = index

    def calculate_offsets(self, start_from=0):
        # truncate the declaration offsets to only that which currently exist
        declarative_length = len(self.declarations)
        self.declaration_offsets = dict(filter(lambda x: x[0] < declarative_length, self.declaration_offsets.items()))
        self.hint_map = dict(filter(lambda x: x[0] < declarative_length, self.hint_map.items()))

        old_bitspan = getattr(self, 'bitspan', None)

        if start_from > 0:
            list_bitspan = sum(map(lambda x: self.declaration_offsets[x]['bitspan'], range(0, start_from)))
        else:
            list_bitspan = 0

        for i in range(start_from, len(self.declarations)):
            declaration = self.declarations[i]

            if declaration.is_size_hint():
                self.map_hint(i)
            elif self.hint_map.has_key(i):
                hint_index = self.hint_map[i]
                hint_object = self.instantiate(hint_index)
                hint_value = hint_object.get_value()

                declaration.args[hint_object.argument] = hint_value

            bitspan = declaration.bitspan()
            alignment = declaration.alignment()
                
            list_bitspan += bitspan

            offset_dict = dict()
            offset_dict['bitspan'] = bitspan

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

            self.declaration_offsets[i] = offset_dict
            
        self.bitspan = list_bitspan

        if not old_bitspan is None and not old_bitspan == self.bitspan and self.is_allocated():
            # TODO compensate for moved data from size-hinted objects changing
            self.reallocate(self.bitspan)

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

        self.declarations.pop(index)

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

        memory_base = self.declaration_offsets[index]['memory_offset'] + self.memory_base
        bitshift = self.declaration_offsets[index]['bitshift']

        instance = self.declarations[index].instantiate(memory_base, bitshift, self)

        return instance

    def __getitem__(self, index):
        return self.instantiate(index)
    
    @classmethod
    def static_bitspan(cls, **kwargs):
        if not cls.DECLARATIONS:
            raise ListError('no static declarations to parse bitspan from')

        # FIXME this doesn't accomodate for odd bitfield alignment.
        # FIXME see calculate_offsets.
        return sum(map(declaration.Declaration.bitspan, cls.DECLARATIONS))

    @classmethod
    def static_declaration(cls, **kwargs):
        kwargs.setdefault('declarations', cls.DECLARATIONS)

        super_class = super(List, cls).static_declaration(**kwargs)

        class StaticList(super_class):
            DECLARATIONS = kwargs['declarations']

        return StaticList
