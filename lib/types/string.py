#!/usr/bin/env python

import ctypes

from paranoia.converters import bitlist_to_bytelist
from paranoia.meta.array import Array, ArrayError
from paranoia.base.memory_region import sizeof
from paranoia.types.char import Char
from paranoia.types.wchar import Wchar

__all__ = ['StringError', 'String', 'WideString']

class StringError(ArrayError):
    pass

class String(Array):
    ZERO_TERMINATED = True
    BASE_DECLARATION = Char
    ELEMENTS = 1 # there's always, at least, a null byte

    def __init__(self, **kwargs):
        self.zero_terminated = kwargs.setdefault('zero_terminated', self.ZERO_TERMINATED)
        self.bind = kwargs.setdefault('bind', self.BIND)

        if not self.bind and not self.zero_terminated:
            raise StringError('cannot have an unbound string with no zero termination')

        Array.__init__(self, **kwargs)

    def parse_data(self, data):
        if not self.is_bound():
            self.elements = len(data)+int(self.zero_terminated)

        for i in xrange(len(data)):
            self[i].set_char_value(data[i])

        if self.zero_terminated:
            self[len(data)].set_value(0)

    def parse_memory(self):
        if self.is_bound():
            maximum = self.elements - int(self.zero_terminated)
        else:
            self.elements = 1
            maximum = None

        chars = list()
        index = 0

        while maximum is None or index < maximum:
            peek = self[index].get_char_value()

            if ord(peek) == 0:
                break

            chars.append(peek)
            index += 1

            if not self.is_bound():
                self.elements += 1

        return ''.join(chars)
        
    def get_value(self):
        if issubclass(self.base_declaration.base_class, Char):
            return str(self)
        elif issubclass(self.base_declaration.base_class, Wchar):
            return unicode(self)
        else:
            raise StringError('unknown base character type')

    def set_value(self, string):
        self.parse_data(string)

    def __str__(self):
        result = list()

        for i in xrange(self.elements):
            c = self[i].get_char_value()

            if ord(c) == 0:
                break
            
            result.append(c)

        return ''.join(result)

    def __unicode__(self):
        result = list()

        for i in xrange(self.elements):
            c = self[i].get_char_value()

            if ord(c) == 0:
                break
            
            result.append(c)

        return u''.join(result)

    @classmethod
    def subclass(cls, **kwargs):
        kwargs.setdefault('zero_terminated', cls.ZERO_TERMINATED)

        super_class = super(String, cls).static_declaration(**kwargs)

        class SubclassedString(super_class):
            ZERO_TERMINATED = kwargs['zero_terminated']

        return SubclassedString

class WideString(String):
    BASE_DECLARATION = Wchar
