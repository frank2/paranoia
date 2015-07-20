#!/usr/bin/env python

from paranoia.base import numeric_region

# technically NumericRegions -are- bitfields, so this is just syntactic sugar.
# though the way they're parsed means we need to set it to BIG_ENDIAN
class Bitfield(numeric_region.NumericRegion):
    ENDIANNESS = numeric_region.NumericRegion.BIG_ENDIAN
    ALIGNMENT = numeric_region.NumericRegion.ALIGN_BIT
