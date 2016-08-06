#!/usr/bin/env python

from paranoia.base import numeric_region

__all__ = ['Bitfield']

class Bitfield(numeric_region.NumericRegion):
    ALIGNMENT = numeric_region.NumericRegion.ALIGN_BIT
