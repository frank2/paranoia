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

        self.overlaps = kwargs.setdefault('overlaps', self.OVERLAPS)
        self.declarations = kwargs.setdefault('declarations', self.DECLARATIONS)
        self.declaration_index = dict()
            
        if self.declarations is None:
            self.declarations = list()

        # if the declarations come from the class definition, copy the instances
        if self.declarations == self.DECLARATIONS:
            self.declarations = map(copy.deepcopy, self.DECLARATIONS)

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
            index = self.declaration_index[id(decl)]
            new_bitcount = align(bitcount, decl.alignment()) + span
            new_bytecount = align(new_bitcount, 8) / 8

            if new_bytecount > bytecount:
                self.write_bytes(bytelist[bytecount:new_bytecount], bytecount)
                instance = self[index]

                try:
                    instance.parse_memory() # TODO make this function a class method
                except NeedMoreDataError:
                    pass

                while instance.bitspan > span:
                    bytecount = new_bytecount
                    new_bitcount = align(span, instance.alignment) + instance.bitspan
                    new_bytecount = align(new_bitcount, 8) / 8
                    self.write_bytes(bytelist[bytecount:new_bytecount], bytecount)
                    span = instance.bitspan
                    instance = self.instantiate(index, reinstance=True)
                
                bytecount = new_bytecount

            bitcount = new_bitcount

    def parse_memory(self):
        if self.mapped:
            return super(List, self).parse_memory()
        
        bytelist = list()
        bitcount = self.bitshift
        bytecount = 0

        for decl in self.map_declarations():
            index = self.declaration_index[id(decl)]
            instance = self[index]
            instance.parse_memory()
            span = instance.bitspan()
            new_bitcount = align(bitcount, instance.alignment) + span
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

            # TODO instead, resolve hints immediately when we come across them
            if i in hint_targets:
                self.instantiate(hint_targets[i]).resolve()
                self.resize(List.declarative_size(self.overlaps, self.declarations))

            self.declare_subregion(decl)
            self.declaration_index[id(decl)] = i
                
            yield decl

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

    def accomodate_subregion(self, decl, new_size):
        if not isinstance(decl, declaration.Declaration):
            raise memory_region.MemoryRegionError('decl must be a Declaration object')

        if not self.has_subregion(decl):
            raise memory_region.MemoryRegionError('subregion not found')

        current_offset = self.subregion_offsets[id(decl)]
        current_index = self.declaration_index[id(decl)]
        size_delta = new_size - decl.bitspan()

        if size_delta == 0:
            return

        if size_delta > 0:
            old_size = decl.get_arg('bitspan')
            decl.set_arg('bitspan', new_size)
            new_size = List.declarative_size(self.overlaps, self.declarations)

            # region must be resized first to accomodate new_size, then other regions
            # can be moved
            self.resize(new_size)

            # set it back to the old size and let resize_subregion do its thing
            decl.set_arg('bitspan', old_size)

            deltas = self.movement_deltas(current_index, size_delta)
            targets = deltas.keys()
            targets.sort()
            targets.reverse()
            reverse_offsets = dict(map(lambda x: x[::-1], self.subregion_offsets.items()))
        
            for offset in targets:
                self.move_subregion(self.subregions[reverse_offsets[offset]], deltas[offset])

        # resize_subregion will handle the other case, where the targets need to be moved *before*
        # resize is called on the list object

    def resize_subregion(self, decl, new_size):
        if not isinstance(decl, declaration.Declaration):
            raise memory_region.MemoryRegionError('decl must be a Declaration object')

        if not self.has_subregion(decl):
            raise memory_region.MemoryRegionError('subregion not found')

        current_offset = self.subregion_offsets[id(decl)]
        current_index = self.declaration_index[id(decl)]
        size_delta = new_size - decl.bitspan()

        if size_delta == 0:
            return

        self.accomodate_subregion(decl, new_size)
        self.remove_subregion(decl)
            
        old_size = decl.get_arg('bitspan')
        decl.set_arg('bitspan', new_size)

        try:
            self.declare_subregion(decl, current_offset)
        except Exception as e:
            decl.set_arg('bitspan', old_size)
            raise e

        if size_delta < 0:
            # subregion shrank, move all subregions
            deltas = self.movement_deltas(current_index, size_delta)
            targets = deltas.keys()
            targets.sort()

            reverse_offsets = dict(map(lambda x: x[::-1], self.subregion_offsets.items()))
        
            for offset in targets:
                self.move_subregion(self.subregions[reverse_offsets[offset]], deltas[offset])

            new_list_size = List.declarative_size(self.overlaps, self.declarations)

            # region can now be resized
            self.resize(new_list_size)

        if not decl.instance is None:
            decl.instance.bitspan = new_size

    def insert_declaration(self, index, decl):
        if self.is_bound():
            raise ListError('cannot alter declarations of bound list after instantiation')

        decl = memory_region.ensure_declaration(decl)
        deltas = self.movement_deltas(index, decl.bitspan())
        self.declarations.insert(index, decl)

        try:
            self.resize(List.declarative_size(self.overlaps, self.declarations))
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
