#!/usr/bin/env python

import inspect

from paranoia.base import declaration, memory_region
from paranoia.meta import list as d_list
from paranoia.converters import align

__all__ = ['ArrayError', 'Array']

class ArrayError(d_list.ListError):
    pass

class Array(d_list.List):
    BASE_DECLARATION = None
    ELEMENTS = 0

    def __init__(self, **kwargs):
        self.base_declaration = kwargs.setdefault('base_declaration', self.BASE_DECLARATION)

        if inspect.isclass(self.base_declaration) and issubclass(self.base_declaration, memory_region.MemoryRegion):
            self.base_declaration = self.base_declaration.declare()

        if self.base_declaration is None:
            raise ArrayError('base declaration cannot be None')

        if not isinstance(self.base_declaration, declaration.Declaration):
            raise ArrayError('base_declaration must be a Declaration instance or MemoryRegion type')
        
        self.elements = kwargs.setdefault('elements', self.ELEMENTS)

        kwargs['declarations'] = [self.base_declaration.copy() for i in xrange(self.elements)]

        d_list.List.__init__(self, **kwargs)

    def set_elements(self, elements):
        if self.bind and self.binding_complete:
            raise ArrayError('cannot resize bound array')

        self.elements = elements
        self.parse_elements()

    def parse_elements(self):
        if self.elements < len(self.declarations):
            for i in range(self.elements, len(self.declarations)):
                self.remove_declaration(self.elements)
        elif self.elements > len(self.declarations):
            old_length = len(self.declarations)
            element_delta = self.elements - old_length

            for i in range(element_delta):
                self.append_declaration(self.base_declaration.copy())

    @classmethod
    def static_bitspan(cls, **kwargs):
        base_decl = kwargs.setdefault('base_declaration', cls.BASE_DECLARATION)
        
        if base_decl is None:
            raise ArrayError('no base declaration to get base bitspan from')

        base_bitspan = base_decl.bitspan()
        elements = kwargs.setdefault('elements', cls.ELEMENTS)
        return base_bitspan * elements
        
    @classmethod
    def static_declaration(cls, **kwargs):
        kwargs.setdefault('base_declaration', cls.BASE_DECLARATION)
        kwargs.setdefault('elements', cls.ELEMENTS)

        super_class = super(Array, cls).static_declaration(**kwargs)

        class StaticArray(super_class):
            BASE_DECLARATION = kwargs['base_declaration']
            ELEMENTS = kwargs['elements']

        return StaticArray
