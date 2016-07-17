#!/usr/bin/env python

import ctypes

from paranoia.meta.array import Array, ArrayError
from paranoia.base.memory_region import sizeof
from paranoia.types.char import Char
from paranoia.types.wchar import Wchar

class StringError(ArrayError):
    pass

class String(Array):
    BASE_CLASS = Char
    BOUND = False
    ELEMENTS = 1 # there's always, at least, a null byte

    def __init__(self, **kwargs):
        self.bound = kwargs.setdefault('bound', self.BOUND)

        string_data = kwargs.setdefault('string_data', self.STRING_DATA)

        if not string_data is None:
            self.elements = len(string_data)+1
        
        Array.__init__(self, **kwargs)

        if self.memory_base and not self.bound:
            self.elements = self.__class__.string_size_from_memory(memory_base=self.memory_base)

    '''
    def instantiate(self, index):
        if self.bound and (index < 0 or index > self.elements):
            raise StringError('index out of bounds')

        instance_address = self.memory_base + (index * sizeof(self.base_class))
        return self.base_class(memory_base=instance_address)
    '''

    def get_value(self):
        return str(self)

    def set_value(self, string):
        limit = len(string)
            
        print '[__str__] before', hex(int(self.memory_base))

        if self.bound and len(string) > self.elements-1:
            limit = self.elements-1
        elif not self.bound:
            self.elements = limit+1

        print '[__str__] after', hex(int(self.memory_base))

        for i in xrange(limit):
            self[i].set_char_value(string[i])

        self[limit].set_value(0)

        print '[set_value] self[0].memory_base =', hex(int(self[0].memory_base))
        print '[set_value] address =', hex(int(self.memory_base))
        print '[set_value] memory =', ctypes.string_at(int(self.memory_base), self.elements)
    
    def __str__(self):
        if not self.bound:
            self.elements = self.__class__.string_size_from_memory(memory_base=self.memory_base)
        
        result = str()
        index = 0

        while 1:
            if self.bound and index > self.elements:
                break

            char_obj = self[index]

            if int(char_obj) == 0:
                break
            
            index += 1
            result += char_obj.get_char_value()

        return result

    @classmethod
    def static_bitspan(cls, **kwargs):
        kwargs.setdefault('memory_base', cls.MEMORY_BASE)
        
        if kwargs['memory_base'] is None:
            return super(String, cls).static_bitspan(**kwargs)

        return cls.string_size_from_memory(**kwargs) * 8

    @classmethod
    def string_size_from_memory(cls, **kwargs):
        kwargs.setdefault('memory_base', cls.MEMORY_BASE)

        if kwargs['memory_base'] is None:
            raise StringError('no memory address provided')

        kwargs.setdefault('base_class', cls.BASE_CLASS)

        if kwargs['base_class'] is None:
            raise StringError('cannot get string bitspan with no base class')

        memory_base = kwargs['memory_base']
        base_class = kwargs['base_class']
        base_size = sizeof(base_class)
        bytespan = 0

        while not ctypes.string_at(int(memory_base)+bytespan, base_size) == '\x00' * base_size:
            bytespan += base_size

        result = (bytespan+base_size)/base_size
        print '[string_size_from_memory] result =', result
        print '[string_size_from_memory] memory =', ctypes.string_at(int(memory_base), result)
        return (bytespan+base_size)/base_size

    @classmethod
    def static_declaration(cls, **kwargs):
        kwargs.setdefault('bound', cls.BOUND)

        super_class = super(String, cls).static_declaration(**kwargs)

        class StaticString(super_class):
            BOUND = kwargs['bound']

        return StaticString
