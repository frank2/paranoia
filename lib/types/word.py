#!/usr/bin/env python

from paranoia.base.size import Size
from paranoia.meta.region import NumericRegion
from paranoia.meta.array import Array

__all__ = ['Word', 'WordArray']

class Word(NumericRegion):
    SIZE = Size(bytes=2)

class WordArray(Array):
    BASE_DECLARATION = Word

