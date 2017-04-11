#!/usr/bin/env python

import copy
import inspect

from paranoia.base import declaration, memory_region, paranoia_agent
from paranoia.meta.size_hint import SizeHint
from paranoia.converters import *

try:
    import __builtin__
except ImportError: # python3
    import builtins as __builtin__

__all__ = ['is_size_hint', 'ListError', 'List']

def is_size_hint(decl):
    return issubclass(decl.base_class, SizeHint)

class ListError(paranoia_agent.ParanoiaError):
    pass

class List(memory_region.MemoryRegion):
    SHRINK = True
    DECLARATIONS = None

    def __init__(self, **kwargs):
        self.mapped = False
        
        self.declarations = kwargs.setdefault('declarations', self.DECLARATIONS)
        self.overlaps = kwargs.setdefault('overlaps', self.OVERLAPS)
        self.declaration_index = dict()
            
        if self.declarations is None:
            self.declarations = list()

        # if the declarations come from the class definition, copy the instances
        if self.declarations == self.DECLARATIONS:
            self.declarations = map(copy.copy, self.DECLARATIONS)

        if not isinstance(self.declarations, list):
            raise ListError('declarations must be a list of Declaration objects')

        self.declarations = map(memory_region.ensure_declaration, self.declarations)
        
        kwargs.setdefault('bitspan', List.declarative_size(self.overlaps, self.declarations))

        memory_region.MemoryRegion.__init__(self, **kwargs)

        self.init_finished = False

        # a call to parse_data might trigger a mapping
        if not self.mapped:
            for decl in self.map_declarations():
                continue

        self.init_finished = True

    def parse_data(self, data):
        if self.mapped:
            super(List, self).parse_data(data)
            return
            
        bytelist = map(ord, list(data))
        bitcount = self.bitshift
        bytecount = 0

        for decl in self.map_declarations():
            span = decl.bitspan()
            new_bitcount = align(bitcount, decl.alignment()) + span
            new_bytecount = align(new_bitcount, 8) / 8

            if new_bytecount > bytecount:
                self.write_bytes(bytelist[bytecount:new_bytecount], bytecount)
                bytecount = new_bytecount

            bitcount = new_bitcount

    def parse_memory(self):
        bytelist = list()
        bitcount = self.bitshift
        bytecount = 0

        for decl in self.map_declarations():
            span = decl.bitspan()
            new_bitcount = align(bitcount, decl.alignment()) + span
            new_bytecount = align(new_bitcount, 8) / 8

            if new_bytecount > bytecount:
                bytelist += self.read_bytes(new_bytecount - bytecount, bytecount)
                bytecount = new_bytecount

            bitcount = new_bitcount

        return ''.join(map(chr, bytelist))
        
    def map_declarations(self):
        if self.mapped:
            raise ListError('list has already been mapped')

        hints = filter(lambda x: is_size_hint(self.declarations[x]), range(len(self.declarations)))
        hint_targets = dict()
        
        for hint_offset in hints:
            hint_decl = self.declarations[hint_offset]
            target_decl = SizeHint.find_target(hint_decl, self, self.declarations)
            hint_targets[target_decl] = hint_offset

        for i in xrange(len(self.declarations)):
            decl = self.declarations[i]
            
            if i in hint_targets:
                self.instantiate(hint_targets[i]).resolve()

            yield decl

            self.declare_subregion(decl)
            self.declaration_index[id(decl)] = i
            
        self.mapped = True

    def movement_deltas(self, index, init_delta):
        if index >= len(self.declarations) or self.overlaps:
            return None

        index_decl = self.declarations[index]
        index_offset = self.subregion_offsets[id(index_decl)]
        current_offsets = filter(lambda x: x[0] >= index_offset if init_delta > 0 else x[0] > index_offset, self.subregion_ranges())
        deltas = dict()
        # reverse offsets are okay because we don't overlap
        reverse_offsets = dict(map(lambda x: x[::-1], self.subregion_offsets.items()))
        prior_delta = None

        for offset in current_offsets:
            offset, size = offset
            ident = reverse_offsets[offset]
                
            if prior_delta is None:
                deltas[offset] = align(offset + init_delta, index_decl.alignment())
            else:
                deltas[offset] = align(offset + prior_delta, self.subregions[ident].alignment())
                
            prior_delta = deltas[offset] - offset

        return deltas

    def insert_declaration(self, index, decl):
        if self.is_bound():
            raise ListError('cannot alter declarations of bound list after instantiation')

        decl = memory_region.ensure_declaration(decl)
        deltas = self.movement_deltas(index, decl.bitspan())
        self.declarations.insert(index, decl)

        #try:
        self.resize(List.declarative_size(self.overlaps, self.declarations))
        #except Exception,e:
        #    self.declarations.pop(index)
        #    raise e

        if not deltas is None:
            targets = deltas.keys()
            targets.sort()
            targets.reverse()
            reverse_offsets = dict(map(lambda x: x[::-1], self.subregion_offsets.items()))

            for offset in targets:
                self.move_subregion(self.subregions[reverse_offsets[offset]], deltas[offset])

        self.declaration_index[id(decl)] = index

        if self.overlaps:
            index = 0

        if not index == 0:
            prev_decl = self.declarations[index-1]
            prev_offset = self.subregion_offsets[id(prev_decl)]
            prev_size = prev_decl.bitspan()
            index = align(prev_offset + prev_size, decl.alignment())
            
        self.declare_subregion(decl, index)

        return decl

    def remove_declaration(self, index):
        if self.is_bound():
            raise ListError('cannot alter declarations of bound list after instantiation')

        decl = self.declarations[index]
        deltas = self.movement_deltas(index, -decl.bitspan())
        removed_decl = self.declarations.pop(index)

        try:
            self.remove_subregion(removed_decl)
        except Exception,e:
            self.declarations.insert(index, removed_decl)
            raise e

        del self.declaration_index[id(removed_decl)]

        if not deltas is None:
            targets = deltas.keys()
            targets.sort()
            reverse_offsets = dict(map(lambda x: x[::-1], self.subregion_offsets.items()))
            
            for offset in targets:
                self.move_subregion(self.subregions[reverse_offsets[offset]], deltas[offset])

        self.resize(List.declarative_size(self.overlaps, self.declarations))

    def append_declaration(self, decl):
        self.insert_declaration(len(self.declarations), decl)

    def instantiate(self, index, **kwargs):
        decl = self.declarations[index]
        offset = self.subregion_offsets[id(decl)]
        kwargs.setdefault('parent_region', self)

        if decl.instance is None or 'reinstance' in kwargs and kwargs['reinstance'] == True:
            return decl.instantiate(**kwargs)

        return decl.instance

    def read_memory(self):
        # initialize all the arguments to get the most accurate read-out of
        # what should be in the object
        for i in range(len(self.declarations)):
            self.instantiate(i)

        return super(List, self).read_memory()

    def __getitem__(self, index):
        return self.instantiate(index)

    def __len__(self):
        return len(self.declarations)

    def __iter__(self):
        for i in xrange(len(self)):
            yield self.instantiate(i)

    @staticmethod
    def declarative_size(overlap, declarations):
        size = 0
        offset = 0

        for decl in declarations:
            decl = memory_region.ensure_declaration(decl)
            
            if overlap:
                if decl.bitspan() > size:
                    size = decl.bitspan()
            else:
                if not decl.bitspan() == 0:
                    size = align(offset, decl.alignment()) + decl.bitspan()
                    
                offset = size

        return size

    @classmethod
    def static_bitspan(cls, **kwargs):
        declarations = kwargs.setdefault('declarations', cls.DECLARATIONS)
        declarations = map(memory_region.ensure_declaration, declarations)
        overlaps = kwargs.setdefault('overlaps', cls.OVERLAPS)

        return cls.declarative_size(overlaps, declarations)

    @classmethod
    def subclass(cls, **kwargs):
        kwargs.setdefault('declarations', cls.DECLARATIONS)

        super_class = super(List, cls).subclass(**kwargs)

        class SubclassedList(super_class):
            DECLARATIONS = kwargs['declarations']

        return SubclassedList
