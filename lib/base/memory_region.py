#!/usr/bin/env python

import ctypes

from paranoia.base import paranoia_agent
from paranoia.base.converters import *

class MemoryRegionError(paranoia_agent.ParanoiaError):
    pass

class MemoryRegion(paranoia_agent.ParanoiaAgent):
    BITSPAN = None
    MEMORY_BASE = None
    BITSHIFT = 0
    VIRTUAL_BASE = 0
    ALIGNMENT = 8

    def __init__(self, **kwargs):
        self.alignment = kwargs.setdefault('alignment', self.ALIGNMENT)
        self.bitspan = kwargs.setdefault('bitspan', self.BITSPAN)
        self.memory_base = kwargs.setdefault('memory_base', self.MEMORY_BASE)
        self.bitshift = kwargs.setdefault('bitshift', self.BITSHIFT)
        self.virtual_base = kwargs.setdefault('virtual_base', self.VIRTUAL_BASE)

        if self.alignment is None or self.alignment < 0:
            raise MemoryRegionError('alignment cannot be None or less than 0')

        if self.bitspan is None or self.bitspan == 0:
            raise MemoryRegionError('bitspan cannot be None or 0')

        if self.memory_base is None:
            raise MemoryRegionError('memory_base cannot be None')

        if self.bitshift > self.alignment or self.bitshift < 0:
            raise MemoryRegionError('bitshift must be within the range of 0-%d noninclusive' % self.alignment)

    def read_bytes(self, byte_length, byte_offset=0):
        if (byte_length+byte_offset)*8 > align(self.bitspan, 8): 
            raise MemoryRegionError('byte length and offset exceed aligned bitspan')

        try:
            return map(ord, ctypes.string_at(self.memory_base+byte_offset, byte_length))
        except:
            raise MemoryRegionError('raw memory access failed')

    def read_bits_from_bytes(self, bit_length, bit_offset=0):
        # true_offset represents where in the first byte to start reading bits
        true_offset = self.bitshift + bit_offset

        if bit_length + bit_offset > self.bitspan:
            raise MemoryRegionError('bit length and offset exceed bitspan')

        # get the number of bytes necessary to grab our contextual bits
        byte_length = align(bit_length+(true_offset % 8), 8)/8

        # convert the bytes into a string of bits
        converted_bytes = ''.join(map('{0:08b}'.format, self.read_bytes(byte_length, true_offset/8)))

        # take only the contextual bits based on the bit_length
        return map(int, converted_bytes)[true_offset:bit_length+true_offset]

    def read_bytes_from_bits(self, bit_length, bit_offset=0):
        return bitlist_to_bytelist(self.read_bits_from_bytes(bit_length, bit_offset))

    def write_bytes(self, byte_list, byte_offset=0):
        if (len(byte_list)+byte_offset)*8 > align(self.bitspan, 8):
            raise MemoryRegionError('list plus offset exceeds memory region boundary')

        string_buffer = ctypes.create_string_buffer(''.join(map(chr, byte_list)))

        try:
            ctypes.memmove(self.memory_base+byte_offset, ctypes.addressof(string_buffer), len(byte_list))
        except:
            raise MemoryRegionError('write exceeds region boundaries')

    def write_bits(self, bit_list, bit_offset=0):
        if len(bit_list) + bit_offset > self.bitspan:
            raise MemoryRegionError('list plus offset exceeds memory region boundary')

        true_offset = self.bitshift + bit_offset
        true_terminus = true_offset + len(bit_list)
        byte_start = true_offset/8
        byte_end = true_terminus/8

        # value represents the number of bits which overwrite the underlying byte
        front_remainder = alignment_delta(true_offset, 8)

        if front_remainder:
            front_bits = bit_list[:front_remainder]
            front_byte_mask = (0xFF ^ (2 ** front_remainder) - 1)
            front_byte_value = self.read_bytes(1, byte_end)[0]
            front_bit_value = bitlist_to_numeric(front_bits)
            mask_result = front_byte_value & front_byte_mask | front_bit_value

            self.write_bytes([mask_result], byte_start)
            byte_start += 1

        # value represents the number of bits which overwrite the underlying byte
        back_remainder = true_terminus % 8

        if back_remainder:
            back_bits = bit_list[len(bit_list) - back_remainder:]
            back_byte_mask = (2 ** back_remainder) - 1
            back_byte_value = self.read_bytes(1, byte_end)[0]
            back_bit_value = bitlist_to_numeric(back_bits)
            mask_result = back_byte_value & back_byte_mask | (back_bit_value << (8 - back_remainder))

            self.write_bytes([mask_result], byte_end)

        bytebound_list = bit_list[front_remainder:(len(bit_list) - back_remainder)]
        bytebound_list = bitlist_to_bytelist(bytebound_list)
        self.write_bytes(bytebound_list, byte_start)

    def write_bits_from_bytes(self, byte_list, bit_offset=0):
        self.write_bits(bytelist_to_bitlist(byte_list), bit_offset)

    def write_bytes_from_bits(self, bit_list, byte_offset=0):
        self.write_bytes(bitlist_to_bytelist(bit_list), byte_offset)

    def __hash__(self):
        return hash('%X/%d/%d' % (self.memory_base, self.bitspan, self.bitshift))

    @classmethod
    def static_bitspan(cls):
        return cls.BITSPAN

    @classmethod
    def static_declaration(cls, **kwargs):
        kwargs.setdefault('bitspan', cls.BITSPAN)
        kwargs.setdefault('memory_base', cls.MEMORY_BASE)
        kwargs.setdefault('bitshift', cls.BITSHIFT)
        kwargs.setdefault('virtual_base', cls.VIRTUAL_BASE)

        class StaticMemoryRegion(cls):
            BITSPAN = kwargs['bitspan']
            MEMORY_BASE = kwargs['memory_base']
            BITSHIFT = kwargs['bitshift']
            VIRTUAL_BASE = kwargs['virtual_base']

        return StaticMemoryRegion
