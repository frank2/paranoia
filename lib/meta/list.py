#!/usr/bin/env python

import copy
import inspect

from paranoia.fundamentals import *
from paranoia.base.paranoia_agent import ParanoiaAgent, ParanoiaError
from paranoia.base.event import *
from paranoia.base.size import Size
from paranoia.meta.declaration import Declaration, ensure_declaration
from paranoia.meta.region import Region, RegionDeclaration, RegionError, RegionDeclarationError
from paranoia.meta.size_hint import SizeHint, SizeHintDeclaration

try:
    import __builtin__
except ImportError: # python3
    import builtins as __builtin__

__all__ = ['ListDeclarationError', 'ListDeclaration', 'ListError', 'List']

class ListDeclarationError(RegionDeclarationError):
    pass

class ListDeclaration(RegionDeclaration):
    def __init__(self, **kwargs):
        super(ListDeclaration, self).__init__(**kwargs)

        if self.get_arg('declarations') is None:
            self.set_arg('declarations', list())
            
        self.declaration_index = dict()
        self.map_declarations()

    def map_declarations(self):
        declarations = self.get_arg('declarations')

        self.set_size(self.declarative_size())
        
        for i in xrange(len(declarations)):
            decl = declarations[i]
            self.declare_subregion(decl)
            self.declaration_index[id(decl)] = i

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
            offset = decl.align(offset, shift) - shift
            decl_size = decl.size()

            if decl_size is None:
                decl_size = decl.declarative_size()
                
            offset += int(decl_size)

        return Size(bits=offset - shift)

    def insert_declaration(self, index, decl):
        if self.is_bound():
            raise ListDeclarationError('cannot alter declarations of bound list after instantiation')

        declarations = self.get_arg('declarations')
        decl = ensure_declaration(decl)
        declarations.insert(index, decl)

        for decl_index in range(index, len(declarations)):
            target_decl = declarations[decl_index]
            self.declaration_index[id(target_decl)] = decl_index

        self.set_size(self.declarative_size())
        shift = self.get_arg('shift')

        if index+1 < len(declarations):
            self.push_subregions(declarations[index+1], decl.size(), True)

        if index == 0:
            offset = 0
        else:
            prev_decl = declarations[index-1]
            prev_offset = self.subregion_offsets[id(prev_decl)]
            offset = decl.align(prev_offset+int(prev_decl.size()), shift) - shift
            
        self.declare_subregion(decl, offset)

        return decl

    def remove_declaration(self, index):
        if self.is_bound():
            raise ListDeclarationError('cannot alter declarations of bound list after instantiation')

        declarations = self.get_arg('declarations')
        removed_decl = declarations.pop(index)

        try:
            self.remove_subregion(removed_decl)
        except Exception,e:
            declarations.insert(index, removed_decl)
            raise e

        for decl_index in range(index, len(declarations)):
            target_decl = declarations[decl_index]
            self.declaration_index[id(target_decl)] = decl_index

        del self.declaration_index[id(removed_decl)]

        if not index >= len(declarations):
            self.push_subregions(declarations[index], -int(removed_decl.size()), True)

        self.set_size(self.declarative_size())

    def append_declaration(self, decl):
        declarations = self.get_arg('declarations')

        if declarations is None:
            raise ListDeclarationError('declarations cannot be None')
        
        self.insert_declaration(len(declarations), decl)

class ListError(ParanoiaError):
    pass

class ListResizeEvent(NewSizeEvent):
    def __call__(self, decl, old_size, new_size):
        delta = int(new_size) - int(old_size)

        if delta == 0:
            return

        parent_decl = decl.get_arg('parent_declaration')

        if delta > 0:
            parent_decl.set_size(parent_decl.declarative_size())
            parent_decl.push_subregions(decl, delta)
        else:
            parent_decl.push_subregions(decl, delta)
            parent_decl.set_size(parent_decl.declarative_size())
            
class List(Region):
    SHRINK = True
    RESIZE_EVENT = ListResizeEvent
    DECLARATIONS = None
    DECLARATION_CLASS = ListDeclaration

    def __init__(self, **kwargs):
        self.declarations = kwargs.setdefault('declarations', self.DECLARATIONS)

        if not self.declarations is None and self.declarations == self.DECLARATIONS:
            self.declarations = map(Declaration.copy, map(ensure_declaration, self.declarations))
            kwargs['declarations'] = self.declarations
        
        super(List, self).__init__(**kwargs)

        self.resolve_hints()

    def resolve_hints(self):
        for i in xrange(len(self.declarations)):
            decl = self.declarations[i]

            if isinstance(decl, SizeHintDeclaration):
                hint_instance = self.instantiate(i)
                hint_instance.resolve()
            elif isinstance(decl, ListDeclaration):
                list_instance = self.instantiate(i)

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
                data = bit_data[:int(parsed)]
            else:
                data = bit_data[offset:offset+int(parsed)]

            if isinstance(decl, SizeHintDeclaration):
                decl.resolve(bit_data=data)

            if self.overlaps:
                if parsed > total_parsed:
                    total_parsed = int(parsed)

                self.write_bits(data, offset)
            else:
                total_parsed = offset + int(parsed)
                
                self.write_bits(data, offset)

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
                    size = decl.align(offset, shift) + decl.size() - shift
                    
                offset = int(size)

        return size

    @classmethod
    def bit_parser(cls, **kwargs):
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

        offset = 0

        for decl in declarations:
            if overlap:
                parsed = decl.bit_parser(bit_data=bit_data)

                if parsed > size:
                    size = parsed
            else:
                offset = decl.align(offset, shift) - shift
                parsed = decl.bit_parser(bit_data=bit_data[offset:])
                size = offset + int(parsed)
                
                if isinstance(decl, SizeHintDeclaration):
                    decl.resolve(parent_declaration=declaration
                                 ,bit_data=bit_data[offset:size])

                offset = size

        return Size(bits=size)

    @classmethod
    def subclass(cls, **kwargs):
        kwargs.setdefault('declarations', cls.DECLARATIONS)

        super_class = super(List, cls).subclass(**kwargs)

        class SubclassedList(super_class):
            DECLARATIONS = kwargs['declarations']

        return SubclassedList

    @classmethod
    def declare(cls, **kwargs):
        declarations = kwargs.setdefault('declarations', cls.DECLARATIONS)

        super_decl = super(List, cls).declare(**kwargs)
        super_decl.base_class = cls

        return super_decl

ListDeclaration.BASE_CLASS = List
