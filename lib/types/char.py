#!/usr/bin/env python

from paranoia.meta.array import Array
from paranoia.meta.region import NumericRegion, RegionError
from paranoia.types.byte import Byte

__all__ = ['CharError', 'Char', 'CharArray']

class CharError(RegionError):
    pass

class Char(Byte):
    def get_char_value(self):
        return chr(self.get_value())

    def set_char_value(self, char):
        if not isinstance(char, str):
            raise CharError('input value must be a string')

        if len(char) > 1:
            raise CharError('input string can only be one character long')

        self.set_value(ord(char))

class CharArray(Array):
    BASE_DECLARATION = Char
