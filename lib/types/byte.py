#!/usr/bin/env python

from paranoia.base.size import Size
from paranoia.meta.region import NumericRegion
from paranoia.meta.array import Array

__all__ = ['Byte', 'ByteArray']

class Byte(NumericRegion):
    SIZE = Size(bytes=1)

class ByteArray(Array):
    BASE_DECLARATION = Byte

    def __str__(self):
        result = list()

        for i in range(self.elements):
            result.append(chr(self[i].get_value()))

        return ''.join(result)

            
