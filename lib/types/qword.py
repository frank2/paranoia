#!/usr/bin/env python

from paranoia.base import numeric_region
from paranoia.meta import array

__all__ = ['Qword', 'QwordArray']

class Qword(numeric_region.NumericRegion):
    BITSPAN = 64

class QwordArray(array.Array):
    BASE_CLASS = Qword
