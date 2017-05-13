#!/usr/bin/env python

import ctypes

from paranoia.fundamentals import align, bitlist_to_bytelist
from paranoia.meta.array import Array, ArrayError
from paranoia.meta.declaration import ensure_declaration
from paranoia.types.char import Char
from paranoia.types.wchar import Wchar

__all__ = ['StringError', 'String', 'WideString']

class StringError(ArrayError):
    pass

class String(Array):
    ZERO_TERMINATED = True
    BASE_DECLARATION = Char
    ELEMENTS = 0

    def __init__(self, **kwargs):
        self.zero_terminated = kwargs.setdefault('zero_terminated', self.ZERO_TERMINATED)

        self.elements = kwargs.setdefault('elements', self.ELEMENTS)

        if self.zero_terminated:
            self.elements += 1
            kwargs['elements'] = self.elements

        Array.__init__(self, **kwargs)

    def parse_bit_data(self, data):
        parsed = self.bit_parser(bit_data=data)

        if not self.is_bound():
            self.set_elements(int(parsed.byte_length() / self.base_declaration.size().byte_length()))
            
        self.write_bits(data[:int(parsed)])

        if not self.zero_terminated:
            zeros = int(parsed - self.elements * self.base_declaration.size())

            if not zeros == 0:
                zero_list = [0] * zeros
                self.write_bits(zero_list, int(parsed))

        return parsed
        
    def parse_memory(self):
        if not self.zero_terminated:
            maximum = self.elements
        else:
            self.set_elements(1)
            maximum = None
            
        index = 0

        while maximum is None or index < maximum:
            char_obj = self[index]
            peek = char_obj.get_char_value()

            if self.zero_terminated and ord(peek) == 0:
                break

            index += 1

            if not self.is_bound():
                self.set_elements(index)

        return self.parse_block_data(self.read_blocks())
        
    def get_value(self):
        if issubclass(self.base_declaration.base_class, Char):
            return str(self)
        elif issubclass(self.base_declaration.base_class, Wchar):
            return unicode(self)
        else:
            raise StringError('unknown base character type')

    def set_value(self, string):
        self.parse_link_data(string)

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
    def bit_parser(cls, **kwargs):
        if 'bit_data' in kwargs:
            bit_data = kwargs['bit_data']
            bit_data += [0] * (8 - len(bit_data))
            links = bitlist_to_bytelist(bit_data)
        elif 'link_data' in kwargs:
            if isinstance(kwargs['link_data'], str):
                links = map(ord, kwargs['link_data'])
            else:
                links = kwargs['link_data']
        elif 'block_data' in kwargs:
            bit_data = bytelist_to_bitlist(kwargs['block_data'])
            shift = kwargs.setdefault('shift', cls.SHIFT)
            bit_data = bit_data[shift:]
            links = bitlist_to_bytelist(bit_data)
        else:
            raise RegionError('no data to parse')

        zero_terminated = kwargs.setdefault('zero_terminated', cls.ZERO_TERMINATED)
        elements = kwargs.setdefault('elements', cls.ELEMENTS)
        base_declaration = kwargs.setdefault('base_declaration', cls.BASE_DECLARATION)
        base_declaration = ensure_declaration(base_declaration)

        if not zero_terminated:
            maximum = elements
        
        chars = list()

        while len(links):
            value = base_declaration.base_class.static_value(link_data=links)
            chars.append(value)
            links = links[base_declaration.size().byte_length():]
    
        if not zero_terminated:
            return len(chars[:maximum])*base_declaration.size()

        zero_index = 0

        for i in xrange(len(chars)):
            char = chars[i]
            
            if char == 0:
                zero_index = i
                break
            
        return len(chars[:zero_index+1])*base_declaration.size()

    @classmethod
    def subclass(cls, **kwargs):
        kwargs.setdefault('zero_terminated', cls.ZERO_TERMINATED)

        super_class = super(String, cls).static_declaration(**kwargs)

        class SubclassedString(super_class):
            ZERO_TERMINATED = kwargs['zero_terminated']

        return SubclassedString

class WideString(String):
    BASE_DECLARATION = Wchar
