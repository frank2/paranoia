#!/usr/bin/env python

from paranoia.base.abstract.array import Array, ArrayError
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
        
        Array.__init__(self, **kwargs)

    def instantiate(self, index):
        # so very unsafe. but so are strings! :)
        # this is done to allow infinite indexing on strings while not
        # treating strings as a pointer

        if self.bound and (index < 0 or index > self.elements):
            raise StringError('index out of bounds')
        
        instance_address = self.memory_base + (index * sizeof(self.base_class))
        return self.base_class(memory_base=instance_address
                               ,parent_region=self)

    def get_value(self):
        return str(self)

    def set_value(self, string):
        limit = len(string)

        if self.bound and len(string) > self.elements-1:
            limit = self.elements-1
            
        for i in xrange(limit):
            self[i].set_char_value(string[i])

        self[limit].set_value(0)
    
    def __str__(self):
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
    def static_declaration(cls, **kwargs):
        kwargs.setdefault('bound', cls.BOUND)

        super_class = super(String, cls).static_declaration(**kwargs)

        class StaticString(super_class):
            BOUND = kwargs['bound']

        return StaticString
