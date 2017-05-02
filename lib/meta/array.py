#!/usr/bin/env python

import inspect

from paranoia.fundamentals import align
from paranoia.base import Size
from paranoia.meta.declaration import Declaration, ensure_declaration
from paranoia.meta.list import ListError, List

__all__ = ['ArrayError', 'Array']

class ArrayError(ListError):
    pass

class Array(List):
    BASE_DECLARATION = None
    ELEMENTS = 0

    def __init__(self, **kwargs):
        self.base_declaration = kwargs.setdefault('base_declaration', self.BASE_DECLARATION)

        if self.base_declaration is None:
            raise ArrayError('base declaration cannot be None')

        self.base_declaration = ensure_declaration(self.base_declaration)
        self.elements = kwargs.setdefault('elements', self.ELEMENTS)

        kwargs['declarations'] = [self.base_declaration.copy() for i in xrange(self.elements)]

        super(Array, self).__init__(**kwargs)

    def set_elements(self, elements):
        self.elements = elements
        # the rest is handled by __setattr__

    def get_elements(self):
        return self.elements

    def parse_elements(self):
        if self.elements == len(self.declarations):
            return

        if self.is_bound():
            raise ArrayError('cannot resize bound array')

        if self.elements < len(self.declarations):
            for i in range(self.elements, len(self.declarations)):
                self.remove_declaration(self.elements)
        elif self.elements > len(self.declarations):
            old_length = len(self.declarations)
            element_delta = self.elements - old_length

            for i in range(element_delta):
                self.append_declaration(self.base_declaration.copy())
                            
    def __setattr__(self, attr, value):
        if attr == 'elements':
            if 'elements' in self.__dict__:
                self.__dict__['elements'] = value

                if 'declaration' in self.__dict__ and not self.__dict__['declaration'] is None:
                    self.__dict__['declaration'].set_arg('elements', value)

                self.parse_elements()
            else:
                self.__dict__[attr] = value
        else:
            super(Array, self).__setattr__(attr, value)

    @classmethod
    def static_size(cls, **kwargs):
        base_decl = kwargs.setdefault('base_declaration', cls.BASE_DECLARATION)
        
        if base_decl is None:
            raise ArrayError('no base declaration to get base size from')

        base_decl = ensure_declaration(base_decl)
        base_size = base_decl.size()
        elements = kwargs.setdefault('elements', cls.ELEMENTS)
        return base_size * elements

    @classmethod
    def bit_parser(cls, **kwargs):
        base_decl = kwargs.setdefault('base_declaration', cls.BASE_DECLARATION)
        
        if base_decl is None:
            raise ArrayError('no base declaration to get base bitspan from')

        base_decl = ensure_declaration(base_decl)
        elements = kwargs.setdefault('elements', cls.ELEMENTS)
        kwargs['declarations'] = [base_decl.copy() for i in xrange(elements)]
        
        return super(Array, cls).bit_parser(**kwargs)
        
    @classmethod
    def subclass(cls, **kwargs):
        kwargs.setdefault('base_declaration', cls.BASE_DECLARATION)
        kwargs.setdefault('elements', cls.ELEMENTS)

        super_class = super(Array, cls).subclass(**kwargs)

        class SubclassedArray(super_class):
            BASE_DECLARATION = kwargs['base_declaration']
            ELEMENTS = kwargs['elements']

        return SubclassedArray
