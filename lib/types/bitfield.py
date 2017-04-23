#!/usr/bin/env python

from paranoia.meta.region import NumericRegion

__all__ = ['Bitfield']

class Bitfield(NumericRegion):
    ALIGNMENT = NumericRegion.ALIGN_BIT
    ENDIANNESS = NumericRegion.BIG_ENDIAN
