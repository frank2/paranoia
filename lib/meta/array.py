#!/usr/bin/env python

from paranoia.base import declaration
from paranoia.meta import list as d_list
from paranoia.meta.list import NewList
from paranoia.converters import align

__all__ = ['ArrayError', 'Array']

class ArrayError(d_list.ListError):
    pass

class Array(NewList):
    BASE_DECLARATION = None
    ELEMENTS = 0

    def __init__(self, **kwargs):
        self.base_declaration = kwargs.setdefault('base_declaration', self.BASE_DECLARATION)

        if self.base_declaration is None:
            raise ArrayError('base declaration cannot be None')

        if not isinstance(self.base_declaration, declaration.Declaration):
            raise ArrayError('base_declaration must be a Declaration type')
        
        self.elements = kwargs.setdefault('elements', self.ELEMENTS)

        string_data = kwargs.setdefault('string_data', self.STRING_DATA)

        kwargs['declarations'] = [self.base_declaration.copy() for i in range(self.elements)]

        NewList.__init__(self, **kwargs)

    def parse_string_data(self, string_data):
        base_size = self.base_declaration.bitspan()
        self.elements = int(align(int(len(string_data) / base_size), base_size) / base_size)
        super(Array, self).parse_string_data(string_data)

    def parse_elements(self):
        if self.elements < len(self.declarations):
            for i in range(self.elements, len(self.declarations)):
                self.remove_declaration(self.elements, True)
        elif self.elements > len(self.declarations):
            old_length = len(self.declarations)
            element_delta = self.elements - old_length

            for i in range(element_delta):
                self.append_declaration(self.base_declaration.copy())
            
    def __setattr__(self, attr, value):
        if attr == 'elements':
            if 'elements' in self.__dict__:
                old_value = self.__dict__['elements']
                self.__dict__['elements'] = value

                if 'declaration' in self.__dict__ and not self.__dict__['declaration'] is None:
                    self.__dict__['declaration'].set_arg('elements', value)

                if not old_value == value:
                    self.parse_elements()
            else:
                self.__dict__[attr] = value
        else:
            super(Array, self).__setattr__(attr, value)

    @classmethod
    def static_bitspan(cls, **kwargs):
        base_class = kwargs.setdefault('base_class', cls.BASE_CLASS)
        
        if base_class is None:
            raise ArrayError('no base class to get base bitspan from')

        base_bitspan = base_class.static_bitspan()
        elements = kwargs.setdefault('elements', cls.ELEMENTS)
        return base_bitspan * elements

    @classmethod
    def static_size(cls, size):
        class StaticlySizedArray(cls):
            ELEMENTS = size

        return StaticlySizedArray
        
    @classmethod
    def static_declaration(cls, **kwargs):
        kwargs.setdefault('base_class', cls.BASE_CLASS)
        kwargs.setdefault('elements', cls.ELEMENTS)

        if not kwargs['base_class'] is None and kwargs['elements'] > 0:
            kwargs['declarations'] = [declaration.Declaration(base_class=kwargs['base_class']) for i in range(kwargs['elements'])]

        super_class = super(Array, cls).static_declaration(**kwargs)

        class StaticlyDeclaredArray(super_class):
            BASE_CLASS = kwargs['base_class']
            ELEMENTS = kwargs['elements']

        return StaticlyDeclaredArray
