#!/usr/bin/env python

import ctypes

__all__ = ['aligned', 'alignment_delta', 'align', 'bitlist_to_bytelist', 'bytelist_to_bitlist'
           ,'bitlist_to_numeric', 'numeric_to_bitlist', 'dict_merge', 'string_address']

def aligned(base, alignment):
    return base % alignment == 0

def alignment_delta(base, alignment):
    return (alignment - (base % alignment)) * int(not aligned(base, alignment))

def align(base, alignment):
    return base + alignment_delta(base, alignment)

def bitlist_to_bytelist(bitlist):
    bitlist = bitlist[::-1]
    bytelist = list()
    byte_value = 0
    
    for i in range(len(bitlist)):
        if i % 8 == 0 and not i == 0:
            byte_value = 0

        byte_value |= bitlist[i] << (i % 8)

        # this is the last bit for the byte
        if (i+1) % 8 == 0:
            bytelist.append(byte_value)

    # that's all for the bits, add the last byte value found
    if not len(bitlist) % 8 == 0:
        bytelist.append(byte_value)

    # reverse the bytelist to match the original direction of the bits
    return bytelist[::-1]

def bytelist_to_bitlist(bytelist):
    return list(map(int, ''.join(map('{0:08b}'.format, bytelist))))

def bitlist_to_numeric(bitlist):
    bitlist = bitlist[::-1]

    byte_value = 0

    for i in range(len(bitlist)):
        byte_value |= bitlist[i] << i

    return byte_value

def numeric_to_bitlist(numeric):
    bitlist = list()

    while numeric > 0:
        bitlist.append(numeric & 1)
        numeric >>= 1

    return bitlist[::-1]

def dict_merge(dict_one, dict_two):
    for key in list(dict_two.keys()):
        if key in dict_one:
            continue

        dict_one[key] = dict_two[key]

def string_address(string):
    # /!\ WARNING INCOMING HACK /!\
    key = 'ADNU'
    offset = ctypes.string_at(id(key), 256).index(key)
    # /!\ WARNING INCOMING HACK /!\
    
    return id(string)+offset
