#!/usr/bin/env python

from paranoia.base import numeric_region
from paranoia.meta import array

__all__ = ['Dword', 'DwordArray']

class Dword(numeric_region.NumericRegion):
    BITSPAN = 32

class DwordArray(array.Array):
    BASE_CLASS = Dword
