#!/usr/bin/env python

from paranoia.base.size import Size
from paranoia.meta.region import NumericRegion
from paranoia.meta.array import Array

__all__ = ['Qword', 'QwordArray']

class Qword(NumericRegion):
    SIZE = Size(bytes=8)

class QwordArray(Array):
    BASE_DECLARATION = Qword
