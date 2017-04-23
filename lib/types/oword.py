#!/usr/bin/env python

from paranoia.base.size import Size
from paranoia.meta.region import NumericRegion
from paranoia.meta.array import Array

__all__ = ['Oword', 'OwordArray']

class Oword(NumericRegion):
    BITSPAN = Size(bytes=16)

class OwordArray(array.Array):
    BASE_DECLARATION = Oword
