#!/usr/bin/env python

from paranoia.base.size import Size
from paranoia.meta.region import NumericRegion
from paranoia.meta.array import Array

__all__ = ['Dword', 'DwordArray']

class Dword(NumericRegion):
    SIZE = Size(bytes=4)

class DwordArray(Array):
    BASE_DECLARATION = Dword
