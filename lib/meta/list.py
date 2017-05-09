#!/usr/bin/env python

import copy
import inspect

from paranoia.fundamentals import *
from paranoia.base.paranoia_agent import ParanoiaAgent, ParanoiaError
from paranoia.base.size import Size
from paranoia.meta.declaration import Declaration, ensure_declaration
from paranoia.meta.region import Region, RegionDeclaration, RegionError, RegionDeclarationError
from paranoia.meta.size_hint import SizeHint

try:
    import __builtin__
except ImportError: # python3
    import builtins as __builtin__

__all__ = ['is_size_hint', 'ListDeclarationError', 'ListDeclaration', 'ListError'
           ,'List']

def is_size_hint(decl):
    return issubclass(decl.base_class, SizeHint)

class ListDeclarationError(RegionDeclarationError):
    pass

class ListDeclaration(RegionDeclaration):
    def __init__(self, **kwargs):
        super(ListDeclaration, self).__init__(**kwargs)

        if self.get_arg('declarations') is None:
            self.set_arg('declarations', list())
            
        self.declaration_index = dict()
        self.map_declarations()
        self.set_arg('size', self.declarative_size())

    def size(self, **kwargs):
        dict_merge(kwargs, self.args)

        size = self.get_arg('size')

        if size is None or int(size) == 0:
            size = self.declarative_size(**kwargs)

            if size is None or int(size) == 0:
                size = self.base_class.static_size(**kwargs)

        return size

    def declarative_size(self, **kwargs):
        dict_merge(kwargs, self.args)

        declarations = kwargs.get('declarations')

        if len(declarations) == 0:
            return Size(bits=0)

        offset = 0
        shift = kwargs.get('shift')

        if shift is None:
            shift = self.get_arg('shift')

        for decl in declarations:
            offset = decl.align(offset, shift)
            offset += int(decl.size())

        return Size(bits=offset)
              
    def map_declarations(self):
        from paranoia.meta.size_hint import SizeHintDeclaration

        for id_val in self.subregions:
            self.remove_subregion(self.subregions[id_val])

        declarations = self.get_arg('declarations')
        declarations = map(ensure_declaration, declarations)
        self.set_arg('declarations', declarations)
        
        shift = self.get_arg('shift')

        for i in xrange(len(declarations)):
            decl = declarations[i]

            self.declare_subregion(decl)
            self.declaration_index[id(decl)] = i

            if isinstance(decl, SizeHintDeclaration):
                decl.resolve()

    def movement_deltas(self, index, init_delta):
        overlaps = self.get_arg('overlaps')
        declarations = self.get_arg('declarations')

        if index >= len(declarations) or overlaps:
            return None

        index_decl = declarations[index]
        index_offset = self.subregion_offsets[id(index_decl)]
        current_offsets = filter(lambda x: x[0] >= index_offset if init_delta > 0 else x[0] > index_offset, self.subregion_ranges())
        deltas = dict()
        # reverse offsets are okay because we don't overlap
        reverse_offsets = dict(map(lambda x: x[::-1], self.subregion_offsets.items()))
        prior_delta = None
        shift = self.get_arg('shift')

        for offset in current_offsets:
            offset, size = offset
            ident = reverse_offsets[offset]
                
            if prior_delta is None:
                deltas[offset] = index_decl.align(offset + init_delta, shift)
            else:
                deltas[offset] = self.subregions[ident].align(offset + prior_delta, shift)
                
            prior_delta = deltas[offset] - offset

        return deltas

    def accomodate_subregion(self, decl, new_size):
        if not isinstance(decl, RegionDeclaration):
            raise ListDeclarationError('decl must be a Declaration object')

        if not self.has_subregion(decl):
            raise ListDeclarationError('subregion not found')

        current_offset = self.subregion_offsets[id(decl)]
        current_index = self.declaration_index[id(decl)]
        size_delta = new_size - decl.size()

        if size_delta == 0:
            return

        if size_delta > 0:
            old_size = decl.size()
            decl.set_arg('size', new_size)
            new_size = self.declarative_size()

            self.set_size(new_size)

            # set it back to the old size and let resize_subregion do its thing
            decl.set_arg('size', old_size)

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
        if not isinstance(decl, Declaration):
            raise ListDeclarationError('decl must be a Declaration object')

        if not self.has_subregion(decl):
            raise ListDeclarationError('subregion not found')

        if not isinstance(new_size, Size):
            raise ListDeclarationError('new_size must be a Size object')

        current_offset = self.subregion_offsets[id(decl)]
        current_index = self.declaration_index[id(decl)]
        size_delta = new_size - decl.size()

        if size_delta == 0:
            return

        self.accomodate_subregion(decl, new_size)
        self.remove_subregion(decl) # detaches declaration from parent
            
        old_size = decl.size()
        decl.set_size(new_size)

        try:
            self.declare_subregion(decl, current_offset)
        except Exception as e:
            decl.set_size(old_size)
            raise e

        if size_delta < 0:
            # subregion shrank, move all subregions
            deltas = self.movement_deltas(current_index, size_delta)
            targets = deltas.keys()
            targets.sort()

            reverse_offsets = dict(map(lambda x: x[::-1], self.subregion_offsets.items()))
        
            for offset in targets:
                self.move_subregion(self.subregions[reverse_offsets[offset]], deltas[offset])

            new_list_size = self.declarative_size()

            # region can now be resized
            self.set_size(new_list_size)

        if not decl.instance is None:
            decl.instance.size = new_size

    def insert_declaration(self, index, decl):
        if self.is_bound():
            raise ListDeclarationError('cannot alter declarations of bound list after instantiation')

        declarations = self.get_arg('declarations')
        decl = ensure_declaration(decl)
        deltas = self.movement_deltas(index, int(decl.size()))
        declarations.insert(index, decl)
        overlaps = self.get_arg('overlaps')

        try:
            self.set_size(self.declarative_size())
        except Exception,e:
            declarations.pop(index)
            raise e

        if not deltas is None:
            targets = deltas.keys()
            targets.sort()
            targets.reverse()
            reverse_offsets = dict(map(lambda x: x[::-1], self.subregion_offsets.items()))

            for offset in targets:
                self.move_subregion(self.subregions[reverse_offsets[offset]], deltas[offset])

        self.declaration_index[id(decl)] = index

        if overlaps:
            index = 0

        shift = self.get_arg('shift')

        if not index == 0:
            prev_decl = declarations[index-1]
            prev_offset = self.subregion_offsets[id(prev_decl)]
            prev_size = prev_decl.size()
            index = decl.align(prev_offset + int(prev_size), shift)
            
        self.declare_subregion(decl, index)

        return decl

    def remove_declaration(self, index):
        if self.is_bound():
            raise ListDeclarationError('cannot alter declarations of bound list after instantiation')

        declarations = self.get_arg('declarations')
        decl = declarations[index]
        deltas = self.movement_deltas(index, -int(decl.size()))
        removed_decl = declarations.pop(index)

        try:
            self.remove_subregion(removed_decl)
        except Exception,e:
            declarations.insert(index, removed_decl)
            raise e

        del self.declaration_index[id(removed_decl)]

        if not deltas is None:
            targets = deltas.keys()
            targets.sort()
            reverse_offsets = dict(map(lambda x: x[::-1], self.subregion_offsets.items()))
            
            for offset in targets:
                self.move_subregion(self.subregions[reverse_offsets[offset]], deltas[offset])

        self.set_size(self.declarative_size())

    def append_declaration(self, decl):
        declarations = self.get_arg('declarations')

        if declarations is None:
            raise ListDeclarationError('declarations cannot be None')
        
        self.insert_declaration(len(declarations), decl)

class ListError(ParanoiaError):
    pass

class List(Region):
    SHRINK = True
    DECLARATIONS = None
    DECLARATION_CLASS = ListDeclaration

    def __init__(self, **kwargs):
        self.declarations = kwargs.setdefault('declarations', self.DECLARATIONS)

        if not self.declarations is None and self.declarations == self.DECLARATIONS:
            self.declarations = map(Declaration.copy, self.declarations)
            kwargs['declarations'] = declarations
        
        super(List, self).__init__(**kwargs)

    def parse_bit_data(self, bit_data):
        total_parsed = 0

        for decl in self.declarations:
            if self.overlaps:
                offset = 0
                parsed = decl.bit_parser(bit_data=bit_data)
            else:
                offset = self.declaration.subregion_offsets[id(decl)]
                parsed = decl.bit_parser(bit_data=bit_data[offset:])
            
            if not parsed == decl.size():
                decl.set_size(parsed)

            if self.overlaps:
                if parsed > total_parsed:
                    total_parsed = int(parsed)

                self.write_bits(bit_data[:int(parsed)], offset)
            else:
                total_parsed = offset + int(parsed)
                
                self.write_bits(bit_data[offset:offset+int(parsed)], offset)

        self.flush()

        return total_parsed

    def read_memory(self):
        # initialize all the arguments to get the most accurate read-out of
        # what should be in the object
        for i in range(len(self.declarations)):
            self.instantiate(i)

        return super(List, self).read_memory()

    def instantiate(self, index, **kwargs):
        decl = self.declarations[index]

        if decl.instance is None or 'reinstance' in kwargs and kwargs['reinstance'] == True:
            return decl.instantiate(**kwargs)

        return decl.instance

    def __getitem__(self, index):
        return self.instantiate(index)

    def __setitem__(self, index, value):
        self.instantiate(index).set_value(value)

    def __len__(self):
        return len(self.declarations)

    def __iter__(self):
        for i in xrange(len(self)):
            yield self.instantiate(i)

    @classmethod
    def static_size(cls, **kwargs):
        size = 0
        offset = 0
        overlap = kwargs.setdefault('overlaps', cls.OVERLAPS)
        shift = kwargs.setdefault('shift', cls.SHIFT)
        declarations = kwargs.setdefault('declarations', cls.DECLARATIONS)

        for decl in declarations:
            decl = ensure_declaration(decl)
            
            if overlap:
                if decl.size() > size:
                    size = decl.size()
            else:
                if not decl.size() == 0:
                    size = decl.align(offset, shift) + decl.size()
                    
                offset = int(size)

        return size

    @classmethod
    def bit_parser(cls, **kwargs):
        from paranoia.meta.size_hint import SizeHintDeclaration
        
        size = 0
        overlap = kwargs.setdefault('overlaps', cls.OVERLAPS)
        shift = kwargs.setdefault('shift', cls.SHIFT)
        declarations = kwargs.setdefault('declarations', cls.DECLARATIONS)
        declaration = kwargs.setdefault('declaration', cls.DECLARATION)

        if declaration is None:
            raise ListError('no declaration provided')

        if declarations is None:
            raise ListError('declarations cannot be None')

        if 'block_data' in kwargs:
            bit_data = bytelist_to_bitlist(kwargs['block_data'])[shift:]
        elif 'byte_data' in kwargs:
            bit_data = bytelist_to_bitlist(kwargs['byte_data'])
        elif 'bit_data' in kwargs:
            bit_data = kwargs['bit_data']
        else:
            bit_data = list()

        for decl in declarations:
            if overlap:
                parsed = decl.bit_parser(bit_data=bit_data)

                if parsed > size:
                    size = parsed
            else:
                size = decl.align(size, shift)
                parsed = decl.bit_parser(bit_data=bit_data[size:])
                
                if isinstance(decl, SizeHintDeclaration):
                    decl.resolve(parent_declaration=declaration
                                 ,bit_data=bit_data[size:])

                size += parsed

        return Size(bits=size)

    @classmethod
    def subclass(cls, **kwargs):
        kwargs.setdefault('declarations', cls.DECLARATIONS)

        super_class = super(List, cls).subclass(**kwargs)

        class SubclassedList(super_class):
            DECLARATIONS = kwargs['declarations']

        return SubclassedList

ListDeclaration.BASE_CLASS = List
