#!/usr/bin/env python

import ctypes
import math
import platform
import sys

__all__ = ['aligned', 'alignment_delta', 'align', 'bitlist_to_bytelist', 'bytelist_to_bitlist'
           ,'bitlist_to_numeric', 'numeric_to_bitlist', 'dict_merge', 'string_address', 'string_offset'
           ,'malloc', 'realloc', 'free', 'memset', 'memmove', 'hexdump', 'bitdump'
           ,'crt_module', 'system', 'arch']
    
# /!\ WARNING INCOMING HACK /!\
key = 'ADNU'
string_offset = ctypes.string_at(id(key), 256).index(key)
# /!\ WARNING INCOMING HACK /!\

crt_module = None
system = platform.system()
arch = int(math.log(sys.maxsize, 2))+1

if system == 'Windows':
    crt_module = ctypes.cdll.msvcrt
elif system.startswith('CYGWIN'):
    crt_module = ctypes.cdll.LoadLibrary('msvcrt.dll')
elif system == 'Linux':
    crt_module = ctypes.cdll.LoadLibrary('libc.so.6')
elif system == 'Darwin':
    crt_module = ctypes.cdll.LoadLibrary('libc.dylib')
else:
    raise RuntimeError('unsupported platform %s' % system)

malloc = crt_module.malloc
malloc.restype = ctypes.c_void_p
malloc.argtypes = (ctypes.c_size_t,)
        
realloc = crt_module.realloc
realloc.restype = ctypes.c_void_p
realloc.argtypes = (ctypes.c_void_p, ctypes.c_size_t)

free = crt_module.free
free.argtypes = (ctypes.c_void_p,)

memset = ctypes.memset
memmove = ctypes.memmove

def hexdump(address, size, label=None):
    data = ctypes.string_at(address, size)
    dump_size = align(size, 16)

    if label is None:
        sys.stdout.write('[hexdump @ %X]\n' % address)
    else:
        sys.stdout.write('[%s @ %X]\n' % (label, address))

    for i in xrange(dump_size):
        if i % 16 == 0:
            sys.stdout.write('[%08X:%04X] ' % ((address+i), i))

        if i < len(data):
            sys.stdout.write('%02X ' % ord(data[i]))
        else:
            sys.stdout.write('   ')

        if i % 16 == 15:
            base = i - 15

            for j in range(base, base+16):
                if j < len(data):
                    char = data[j]
                else:
                    char = ' '
                    
                val = ord(char)

                if 0x20 <= val <= 0x7F:
                    sys.stdout.write('%s' % char)
                else:
                    sys.stdout.write('.')

            sys.stdout.write('\n')

def bitdump(address, bitspan, bit_offset=0, label=None):
    bytelist = map(ord, ctypes.string_at(address, align(bit_offset+bitspan, 8)/8))
    bitlist = list()

    if label is None:
        sys.stdout.write('[bitdump @ %X]\n' % address)
    else:
        sys.stdout.write('[%s @ %X]\n' % (label, address))

    for byte_obj in bytelist:
        value_bits = list()

        for i in xrange(8):
            value_bits.append(byte_obj & 1)
            byte_obj >>= 1

        value_bits.reverse()

        bitlist += value_bits

    byte_iterator = 0
    bit_iterator = 0

    while byte_iterator < align(len(bytelist), 8):
        if byte_iterator % 8 == 0:
            sys.stdout.write('%08X:%04X:X ' % (address+byte_iterator, byte_iterator))

        if byte_iterator < len(bytelist):
            sys.stdout.write('%02X%6s ' % (bytelist[byte_iterator], ''))
        else:
            sys.stdout.write('%8s ' % '')

        if byte_iterator % 8 == 7:
            for i in xrange(8):
                if byte_iterator-7+i >= len(bytelist):
                    break
                    
                byte_val = bytelist[byte_iterator-7+i]

                if byte_val >= 32 and byte_val <= 127:
                    sys.stdout.write(chr(byte_val))
                else:
                    sys.stdout.write('.')
                        
            sys.stdout.write('\n')
            sys.stdout.write('%08X:%04X:B ' % (address+(byte_iterator-7), bit_iterator))
                
            while bit_iterator < len(bitlist):
                if bit_iterator < bit_offset or bit_iterator-bit_offset >= bitspan:
                    sys.stdout.write(' ')
                else:
                    sys.stdout.write('%d' % bitlist[bit_iterator])

                if bit_iterator % 8 == 7:
                    sys.stdout.write(' ')

                bit_iterator += 1

                if bit_iterator % 64 == 0:
                    break

            sys.stdout.write('\n\n')
                
        byte_iterator += 1

def aligned(base, alignment):
    return base % alignment == 0

def alignment_delta(base, alignment):
    modulus = base % alignment
    return (alignment - modulus) * int(not modulus == 0)

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
    global string_offset
    
    return id(string)+string_offset
