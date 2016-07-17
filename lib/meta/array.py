#!/usr/bin/env python

from paranoia.base import declaration
from paranoia.meta import list as d_list
from paranoia.converters import align

class ArrayError(d_list.ListError):
    pass

class Array(d_list.List):
    BASE_CLASS = None
    ELEMENTS = 0

    def __init__(self, **kwargs):
        self.base_class = kwargs.setdefault('base_class', self.BASE_CLASS)
        self.elements = kwargs.setdefault('elements', self.ELEMENTS)

        string_data = kwargs.setdefault('string_data', self.STRING_DATA)

        if self.elements == 0:
            raise ArrayError('elements cannot be 0')

        kwargs['declarations'] = [declaration.Declaration(base_class=self.base_class) for i in xrange(self.elements)]

        if not string_data is None and len(string_data) and self.elements == 0:
            base_size = self.base_class.static_bitspan()
            self.elements = align(len(string_data) / base_size, base_size) / base_size

        d_list.List.__init__(self, **kwargs)

    def parse_elements(self):
        if self.elements < len(self.declarations):
            self.declarations = self.declarations[:self.elements]
            self.calculate_offsets(len(self.declarations)) # truncate declaration_offsets
        elif self.elements > len(self.declarations):
            old_length = len(self.declarations)
            element_delta = self.elements - old_length

            for i in xrange(element_delta):
                self.declarations.append(declaration.Declaration(base_class=self.base_class))
                
            self.calculate_offsets(old_length)
            
    def __setattr__(self, attr, value):
        if attr == 'elements':
            if self.__dict__.has_key('elements'):
                old_value = self.__dict__['elements']
                self.__dict__['elements'] = value

                if self.__dict__.has_key('declaration') and not self.__dict__['declaration'] is None:
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
            kwargs['declarations'] = [declaration.Declaration(base_class=kwargs['base_class']) for i in xrange(kwargs['elements'])]

        super_class = super(Array, cls).static_declaration(**kwargs)

        class StaticlyDeclaredArray(super_class):
            BASE_CLASS = kwargs['base_class']
            ELEMENTS = kwargs['elements']

        return StaticlyDeclaredArray
