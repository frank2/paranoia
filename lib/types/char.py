#!/usr/bin/env python

from paranoia.base import numeric_region
from paranoia.meta import array
from paranoia.types import byte

__all__ = ['CharError', 'Char', 'CharArray']

class CharError(numeric_region.NumericRegionError):
    pass

class Char(byte.Byte):
    def get_char_value(self):
        return chr(self.get_value())

    def set_char_value(self, char):
        if not isinstance(char, str):
            raise CharError('input value must be a string')

        if len(char) > 1:
            raise CharError('input string can only be one character long')

        self.set_value(ord(char))

class CharArray(array.Array):
    BASE_CLASS = Char
