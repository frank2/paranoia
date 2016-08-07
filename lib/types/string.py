#!/usr/bin/env python

import ctypes

from paranoia.meta.array import Array, ArrayError
from paranoia.base.memory_region import sizeof
from paranoia.types.char import Char
from paranoia.types.wchar import Wchar

__all__ = ['StringError', 'String']

class StringError(ArrayError):
    pass

class String(Array):
    BIND = False
    ZERO_TERMINATED = True
    BASE_CLASS = Char
    ELEMENTS = 1 # there's always, at least, a null byte

    def __init__(self, **kwargs):
        string_data = kwargs.setdefault('string_data', self.STRING_DATA)
        self.zero_terminated = kwargs.setdefault('zero_terminated', self.ZERO_TERMINATED)
        self.bind = kwargs.setdefault('bind', self.BIND)

        if not self.bind and not self.zero_terminated:
            raise StringError('cannot have an unbound string with no zero termination')

        if not string_data is None and not self.bind:
            self.elements = len(string_data)+int(self.zero_terminated)
        
        Array.__init__(self, **kwargs)

        if self.memory_base and not self.bind:
            self.elements = self.__class__.string_size_from_memory(memory_base=self.memory_base)

    def get_value(self):
        return str(self)

    def set_value(self, string):
        limit = len(string)
        
        if self.bind and len(string) > self.elements-int(self.zero_terminated):
            limit = self.elements-int(self.zero_terminated)
        elif not self.bind:
            self.elements = limit+int(self.zero_terminated)

        for i in range(limit):
            self[i].set_char_value(string[i])

        if self.zero_terminated:
            self[limit].set_value(0)

    def __str__(self):
        if not self.bind and self.zero_terminated:
            self.elements = self.__class__.string_size_from_memory(memory_base=self.memory_base)
        
        result = str()
        index = 0

        while 1:
            if self.bind and index >= self.elements:
                break

            char_obj = self[index]

            if self.zero_terminated and int(char_obj) == 0:
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

        while not bytearray(ctypes.string_at(int(memory_base)+bytespan, base_size)) == bytearray([0] * base_size):
            bytespan += base_size

        result = int((bytespan+base_size)/base_size)
        return int((bytespan+base_size)/base_size)

    @classmethod
    def static_declaration(cls, **kwargs):
        kwargs.setdefault('bind', cls.BIND)

        super_class = super(String, cls).static_declaration(**kwargs)

        class StaticString(super_class):
            BIND = kwargs['bind']

        return StaticString
