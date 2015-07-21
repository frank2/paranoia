#!/usr/bin/env python

from paranoia.base import numeric_region

class Bitfield(numeric_region.NumericRegion):
    ALIGNMENT = numeric_region.NumericRegion.ALIGN_BIT

    #def write_bits(self, bits, bit_offset=0):
    #    print bits
    #    return super(numeric_region.NumericRegion, self).write_bits(bits[::-1], bit_offset)
    
    #def read_bits_from_bytes(self, bit_length, bit_offset=0):
    #    return super(numeric_region.NumericRegion, self).read_bits_from_bytes(bit_length, bit_offset)[::-1]
