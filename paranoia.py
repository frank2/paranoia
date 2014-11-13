#!/usr/bin/env python

import ctypes
import os
import sys

# the goal is to implement the primitives of C. they are:
#
# * bitfield
# * byte
# * word
# * dword
# * qword
# * char
# * wchar
# * structure
# * union
# * enum
#
# * a bitfield is an arbitrary series of bits
# * a byte is an 8-bit bitfield
# * a word is a 16-bit bitfield
# * a dword is a 32-bit bitfield
# * a qword is a 64-bit bitfield
# * a char is a byte
# * a wchar is a word
# * a structure is an arbitrary series of primitives
# * a union is a structure whose variables all take up the same bit offset
#
# the kicker is that memory regions are in terms of bytes. this means that the
# region underlying all this data needs to be byte-aware but also expose bit-level
# functionality.

def aligned(base, alignment):
    return base % alignment == 0

def alignment_delta(base, alignment):
    return (alignment - (base % alignment)) * int(not aligned(base, alignment))

def align(base, alignment):
    return base + alignment_delta(base, alignment)

def bitlist_to_bytelist(bitlist):
    bitlist += [0] * alignment_delta(len(bitlist), 8)
        
    byte_value = 0
    returned_bytes = list()

    for i in xrange(len(bitlist)):
        if i % 8 == 0:
            byte_value = 0

        byte_value <<= 1
        byte_value |= bitlist[i]

        if (i+1) % 8 == 0:
            returned_bytes.append(byte_value)

    return returned_bytes

def bytelist_to_bitlist(bytelist):
    return map(int, ''.join(map('{0:08b}'.format, bytelist)))

def bitlist_to_numeric(bitlist):
    bitlist = bitlist[::-1]

    byte_value = 0

    for i in xrange(len(bitlist)):
        byte_value <<= 1
        byte_value |= bitlist[i]

    return byte_value

class ParanoiaAgent(object):
    pass

class ParanoiaError(Exception):
    pass

class Address(ParanoiaAgent):
    MEMORY_REGION = None
    BIT_OFFSET = 0

class MemoryRegionError(ParanoiaError):
    pass

class MemoryRegion(ParanoiaAgent):
    BITSPAN = None
    MEMORY_BASE = None
    BITSHIFT = 0
    VIRTUAL_BASE = 0

    def __init__(self, **kwargs):
        self.bitspan = kwargs.setdefault('bitspan', self.BITSPAN)
        self.memory_base = kwargs.setdefault('memory_base', self.MEMORY_BASE)
        self.bitshift = kwargs.setdefault('bitshift', self.BITSHIFT)
        self.virtual_base = kwargs.setdefault('bitshift', self.VIRTUAL_BASE)

        if self.bitspan is None:
            raise MemoryRegionError('bitspan cannot be None')

        if self.memory_base is None:
            raise MemoryRegionError('memory_base cannot be None')

        if self.bitshift > 8 or self.bitshift < 0:
            raise MemoryRegionError('bitshift must be within the range of 0-8 noninclusive')

    def read_bytes(self, byte_length, byte_offset=0):
        if (byte_length+byte_offset)*8 > self.bitspan:
            raise MemoryRegionError('byte length and offset exceed bitspan')

        try:
            return map(ord, ctypes.string_at(self.memory_base+byte_offset, byte_length))
        except:
            raise MemoryRegionError('raw memory access failed')

    def read_bits_from_bytes(self, bit_length, bit_offset=0):
        true_offset = self.bitshift + bit_offset

        if bit_length + bit_offset > self.bitspan:
            raise MemoryRegionError('bit length and offset exceed bitspan')

        byte_length = align(bit_length+(true_offset % 8), 8)/8
        converted_bytes = ''.join(map('{0:08b}'.format, self.read_bytes(byte_length, true_offset/8)))
        return map(int, converted_bytes)[true_offset % 8:bit_length + (true_offset % 8)]

    def read_bytes_from_bits(self, bit_length, bit_offset=0):
        return bitlist_to_bytelist(self.read_bits_from_bytes(bit_length, bit_offset))

    def write_bytes(self, byte_list, byte_offset=0):
        if (len(byte_list)+byte_offset)*8 > self.bitspan:
            raise MemoryRegionError('list plus offset exceeds memory region boundary')

        string_buffer = ctypes.create_string_buffer(''.join(map(chr, byte_list)))

        try:
            ctypes.memmove(self.memory_base+byte_offset, ctypes.addressof(string_buffer), len(byte_list))
        except:
            raise MemoryRegionError('write exceeds region boundaries')

    def write_bits(self, bit_list, bit_offset=0):
        if len(bit_list) + bit_offset > self.bitspan:
            raise MemoryRegionErropr('list plus offset exceeds memory region boundary')

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

class AddressError(ParanoiaError):
    pass

class Address(ParanoiaAgent):
    MEMORY_REGION = None
    BIT_OFFSET = 0

    def __init__(self, **kwargs):
        self.memory_region = kwargs.setdefault('memory_region', self.MEMORY_REGION)

        if kwargs.has_key('byte_offset'):
            self.bit_offset = kwargs['byte_offset'] * 8
        else:
            self.bit_offset = kwargs.setdefault('bit_offset', self.BIT_OFFSET)

        if self.memory_region is None:
            raise AddressError('memory_region cannot be None')

    def byte_offset(self):
        return self.bit_offset/8

    def memory_offset(self):
        return self.byte_offset() + self.memory_region.memory_base

    def virtual_offset(self):
        return self.byte_offset() + self.memory_region.virtual_base

    def cast(self, memory_class, **kwargs):
        byte_shift = self.memory_region.memory_base + self.bit_offset/8
        bit_shift = self.bit_offset % 8

        kwargs['memory_base'] = byte_shift
        kwargs['bitshift'] = bit_shift
        kwargs['virtual_base'] = self.memory_region.virtual_base + byte_shift

        return memory_class(**kwargs)
