#!/usr/bin/env python

from paranoia.base import memory_region
from paranoia.converters import *

__all__ = ['NumericRegionError', 'NumericRegion']

class NumericRegionError(memory_region.MemoryRegionError):
    pass

class NumericRegion(memory_region.MemoryRegion):
    LITTLE_ENDIAN = 0
    BIG_ENDIAN = 1
    ENDIANNESS = 0
    UNSIGNED = 0
    SIGNED = 1
    SIGNAGE = 0
    VALUE = None

    # TODO setattr/getattr to intercept rewrites of value

    def __init__(self, **kwargs):
        self.endianness = kwargs.setdefault('endianness', self.ENDIANNESS)

        if not self.endianness == self.LITTLE_ENDIAN and not self.endianness == self.BIG_ENDIAN:
            raise NumericRegionError('endianness must be NumericRegion.LITTLE_ENDIAN or NumericRegion.BIG_ENDIAN')

        self.signage = kwargs.setdefault('signage', self.SIGNAGE)

        if not self.signage == self.SIGNED and not self.signage == self.UNSIGNED:
            raise NumericRegionError('signage must be NumericRegion.SIGNED or NumericRegion.UNSIGNED')

        memory_region.MemoryRegion.__init__(self, **kwargs)

        value = kwargs.setdefault('value', self.VALUE)

        if not value is None:
            self.set_value(value)

    def get_value(self):
        bitlist = self.read_bits_from_bytes(self.bitspan)
        value = 0

        if self.alignment == self.ALIGN_BYTE:
            bitspan_content = bitlist_to_bytelist(bitlist)

            # the bytelist comes out endian-agnostic, so if it's little endian, we
            # need to reverse it.
            if self.endianness == NumericRegion.LITTLE_ENDIAN:
                bitspan_content = bitspan_content[::-1]

            for i in range(len(bitspan_content)):
                value <<= 8
                value |= bitspan_content[i]
        elif self.alignment == self.ALIGN_BIT:
            value = 0

            for bit in bitlist:
                value <<= 1
                value |= bit

        signed_bit = 2 ** (self.bitspan - 1)
        
        if self.signage == self.SIGNED and value & signed_bit:
            value = value - 2 ** self.bitspan

        return value

    def set_value(self, value):
        bytelist = list()
        bitspan = self.bitspan

        if value < 0:
            value += 2 ** self.bitspan

            if value <= 0:
                raise NumericRegionError('negative overflow')

        value &= (2 ** self.bitspan) - 1

        # we never actually wind up setting value in the declaration args, so
        # do it manually here
        if not self.declaration is None:
            self.declaration.set_arg('value', value)

        if self.alignment == self.ALIGN_BYTE:
            while bitspan > 0:
                bytelist.append(value & 0xFF)
                value >>= 8
                bitspan -= 8

            # bytelist is little endian, so only reverse it if we're big endian
            if self.endianness == NumericRegion.BIG_ENDIAN:
                bytelist = bytelist[::-1]

            bitspan_content = bytelist_to_bitlist(bytelist)

            self.write_bits(bitspan_content)
        elif self.alignment == self.ALIGN_BIT:
            bits = 0
            bitlist = list()

            while value > 0 and bits < self.bitspan:
                bitlist.append(value & 1)
                value >>= 1
                bits += 1

            bitlist.reverse()

            if not len(bitlist) == self.bitspan:
                delta = self.bitspan - len(bitlist)
                bitlist = ([0] * delta) + bitlist

            self.write_bits(bitlist)

    def __int__(self):
        return self.get_value()

    @classmethod
    def static_declaration(cls, **kwargs):
        kwargs.setdefault('endianness', cls.ENDIANNESS)
        kwargs.setdefault('signage', cls.SIGNAGE)
        kwargs.setdefault('value', cls.VALUE)

        super_class = super(NumericRegion, cls).static_declaration(**kwargs)

        class StaticNumericRegion(super_class):
            ENDIANNESS = kwargs['endianness']
            SIGNAGE = kwargs['signage']
            VALUE = kwargs['value']

        return StaticNumericRegion
