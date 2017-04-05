#!/usr/bin/env python

import inspect

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
    BIND = False
    OVERLAPS = False

    def __init__(self, **kwargs):
        self.declarations = kwargs.setdefault('declarations', self.DECLARATIONS)
        self.overlaps = kwargs.setdefault('overlaps', self.OVERLAPS)

        for i in xrange(len(self.declarations)):
            if inspect.isclass(self.declarations[i]) and issubclass(self.declarations[i], memory_region.MemoryRegion):
                self.declarations[i] = self.declarations[i].declare()
                
        # if the declarations come from the class definition, copy the instances
        if self.declarations == self.DECLARATIONS:
            self.declarations = map(declaration.Declaration.copy, self.declarations)
            
        if self.declarations is None:
            self.declarations = list()

        if not isinstance(self.declarations, list):
            raise ListError('declarations must be a list of Declaration objects')

        for d in self.declarations:
            if not isinstance(d, declaration.Declaration):
                raise ListError('declarations must be a list of Declaration objects')

        kwargs.setdefault('bitspan', self.declarative_size())

        memory_region.MemoryRegion.__init__(self, **kwargs)

        self.binding_complete = False
        self.map_declarations()
        self.binding_complete = True

    def declarative_size(self):
        size = 0
        offset = 0

        for decl in self.declarations:
            if self.overlaps:
                if decl.bitspan() > size:
                    size = decl.bitspan()
            else:
                size = align(offset, decl.alignment()) + decl.bitspan()
                offset = size

        return size

    def map_declarations(self):
        if self.is_bound():
            raise ListError('cannot remap bound list')
        
        # in some cases we might have declarations inserted before this is called 
        for decl in self.declarations:
            if not self.has_subregion(decl):
                if self.overlaps:
                    self.declare_subregion(decl, 0)
                else:
                    self.declare_subregion(decl)

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

        if inspect.isclass(decl) and isinstance(decl, memory_region.MemoryRegion):
            decl = decl.declare()

        if not isinstance(decl, declaration.Declaration):
            raise ListError('decl must be a Declaration object')
        
        deltas = self.movement_deltas(index, decl.bitspan())
        self.declarations.insert(index, decl)

        try:
            self.resize(self.declarative_size())
        except Exception,e:
            self.declarations.pop(index)
            raise e

        if not deltas is None:
            targets = deltas.keys()
            targets.sort()
            targets.reverse()
            reverse_offsets = dict(map(lambda x: x[::-1], self.subregion_offsets.items()))

            for offset in targets:
                self.move_subregion(self.subregions[reverse_offsets[offset]], deltas[offset])

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

        if not deltas is None:
            targets = deltas.keys()
            targets.sort()
            reverse_offsets = dict(map(lambda x: x[::-1], self.subregion_offsets.items()))
            
            for offset in targets:
                self.move_subregion(self.subregions[reverse_offsets[offset]], deltas[offset])

        self.resize(self.declarative_size())

    def append_declaration(self, decl):
        self.insert_declaration(len(self.declarations), decl)

    def instantiate(self, index, **kwargs):
        decl = self.declarations[index]
        offset = self.subregion_offsets[id(decl)]

        if decl.instance is None or kwargs.has_key('reinstance') and kwargs['reinstance'] == True:
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

    @classmethod
    def static_bitspan(cls, **kwargs):
        declarations = kwargs.setdefault('declarations', cls.DECLARATIONS)

        for i in xrange(len(declarations)):
            if inspect.isclass(declarations[i]) and issubclass(declarations[i], memory_region.MemoryRegion):
                declarations[i] = declarations[i].declare()
                
        overlaps = kwargs.setdefault('overlaps', cls.OVERLAPS)
        size = 0
        offset = 0

        for decl in declarations:
            if overlaps:
                if decl.bitspan() > size:
                    size = decl.bitspan()
            else:
                size = align(offset, decl.alignment()) + decl.bitspan()
                offset = size

        return size

    @classmethod
    def static_declaration(cls, **kwargs):
        kwargs.setdefault('declarations', cls.DECLARATIONS)
        kwargs.setdefault('bind', cls.BIND)
        kwargs.setdefault('overlaps', cls.OVERLAPS)

        super_class = super(List, cls).static_declaration(**kwargs)

        class StaticList(super_class):
            DECLARATIONS = kwargs['declarations']
            BIND = kwargs['bind']
            OVERLAPS = kwargs['overlaps']

        return StaticList
