#!/usr/bin/env python

from paranoia.base import numeric_region
from paranoia.meta import array

__all__ = ['Word', 'WordArray']

class Word(numeric_region.NumericRegion):
    BITSPAN = 16

class WordArray(array.Array):
    BASE_CLASS = Word

