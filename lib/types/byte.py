#!/usr/bin/env python

from paranoia.base import numeric_region
from paranoia.meta import array

__all__ = ['Byte', 'ByteArray']

class Byte(numeric_region.NumericRegion):
    BITSPAN = 8

class ByteArray(array.Array):
    BASE_CLASS = Byte

    def __str__(self):
        result = list()

        for i in range(self.elements):
            result.append(chr(self[i].get_value()))

        return ''.join(result)

            
