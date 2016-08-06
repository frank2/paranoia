#!/usr/bin/env python

from paranoia.base import numeric_region
from paranoia.meta import array

__all__ = ['Oword', 'OwordArray']

class Oword(numeric_region.NumericRegion):
    BITSPAN = 128

class OwordArray(array.Array):
    BASE_CLASS = Oword
