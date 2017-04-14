#!/usr/bin/env python

import ctypes
import platform
import sys

from paranoia.base.paranoia_agent import ParanoiaError
from paranoia.converters import align

__all__ = ['MemoryError', 'crt_module', 'system', 'malloc', 'realloc', 'free', 'memset', 'memmove', 'hexdump']

class MemoryError(ParanoiaError):
    pass

crt_module = None
system = platform.system()

if system == 'Windows':
    crt_module = ctypes.cdll.msvcrt
elif system.startswith('CYGWIN'):
    crt_module = ctypes.cdll.LoadLibrary('msvcrt.dll')
elif system == 'Linux':
    crt_module = ctypes.cdll.LoadLibrary('libc.so.6')
elif system == 'Darwin':
    crt_module = ctypes.cdll.LoadLibrary('libc.dylib')
else:
    raise MemoryError('unsupported platform %s' % system)

# HERE'S THE PART WHERE I CLEAN UP AFTER CTYPES' MESS
malloc = crt_module.malloc
malloc.restype = ctypes.c_void_p
malloc.argtypes = (ctypes.c_size_t,)
        
realloc = crt_module.realloc
realloc.restype = ctypes.c_void_p
realloc.argtypes = (ctypes.c_void_p, ctypes.c_size_t)

free = crt_module.free
free.argtypes = (ctypes.c_void_p,)

# HERE'S THE PART WHERE CTYPES MAYBE KINDA HELPS
memset = ctypes.memset
memmove = ctypes.memmove

def hexdump(address, size, label=None):
    import sys
    
    data = ctypes.string_at(address, size)
    dump_size = align(size, 16)

    if label is None:
        sys.stdout.write('[hexdump @ %X]\n' % address)
    else:
        sys.stdout.write('[%s @ %X]\n' % (label, address))

    for i in xrange(dump_size):
        if i % 16 == 0:
            sys.stdout.write('[%08X] ' % (address+i))

        if i < len(data):
            sys.stdout.write('%02X ' % ord(data[i]))
        else:
            sys.stdout.write('   ')

        if i % 2 == 1:
            sys.stdout.write('  ')

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
