#!/usr/bin/env python

import cProfile
import ctypes
import os
import sys

import paranoia

def test_MemoryRegion():
    print '[test_MemoryRegion]'

    # allocate a string
    c_string = ctypes.create_string_buffer("MemoryRegion test")
    c_address = ctypes.addressof(c_string)

    # initialize the region
    region = paranoia.MemoryRegion(memory_base=c_address, bitspan=len(c_string)*8)

    # run basic assertions
    assert region.read_bytes(len(c_string)) == map(ord, c_string.raw)
    assert region.read_bytes(len(c_string)-1, 1) == map(ord, c_string.raw[1:])
    print '[MemoryRegion.read_bytes: PASS]'

    assert region.read_bits_from_bytes(4) == [0, 1, 0, 0]
    assert region.read_bits_from_bytes(4, 4) == [1, 1, 0, 1]
    assert region.read_bits_from_bytes(4, 6) == [0, 1, 0, 1]
    print '[MemoryRegion.read_bits_from_bytes: PASS]'

    assert region.read_bytes_from_bits(8, 4) == [int('11010110', 2)]
    assert region.read_bytes_from_bits(6, 4) == [int('11010100', 2)]
    print '[MemoryRegion.read_bytes_from_bits: PASS]'

    region.write_bytes([69, 72, 45, 54], 0)
    assert region.read_bytes(4) == [69, 72, 45, 54]
    region.write_bytes([69, 72, 45, 54], 4)
    assert region.read_bytes(4, 4) == [69, 72, 45, 54]
    region.write_bytes([77], 4)
    assert region.read_bytes(4, 4) == [77, 72, 45, 54]
    print '[MemoryRegion.write_bytes: PASS]'

    region.write_bits([1] * 4)
    assert region.read_bits_from_bytes(4) == [1] * 4
    region.write_bits([1] * 12, 6)
    assert region.read_bits_from_bytes(12, 6) == [1] * 12
    print '[MemoryRegion.write_bits: PASS]'
    

def main(*args):
    test_MemoryRegion()

if __name__ == '__main__':
    cProfile.run('main(*sys.argv[1:])')
