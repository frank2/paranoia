#!/usr/bin/env python

import platform
import ctypes
import traceback

try:
    import __builtin__
except ImportError: # python3
    import builtins as __builtin__

from paranoia.base import paranoia_agent
from paranoia.base import address
from paranoia.converters import string_address

__all__ = ['AllocatorError', 'AllocationError', 'Allocator', 'Allocation']

class AllocatorError(paranoia_agent.ParanoiaError):
    pass

class AllocationError(paranoia_agent.ParanoiaError):
    pass

class Allocator(paranoia_agent.ParanoiaAgent):
    def __init__(self, **kwargs):
        crt_module = None
        system = platform.system()

        if system == 'Windows':
            crt_module = cdll.msvcrt
        elif system.startswith('CYGWIN'):
            crt_module = ctypes.cdll.LoadLibrary('msvcrt.dll')
        elif system == 'Linux' or system.startswith('CYGWIN'):
            crt_module = ctypes.cdll.LoadLibrary('libc.so.6')
        elif system == 'Darwin':
            crt_module = ctypes.cdll.LoadLibrary('libc.dylib')
        else:
            AllocatorError('unsupported platform %s' % system)

        # HERE'S THE PART WHERE I CLEAN UP AFTER CTYPES' MESS
        self.crt_malloc = crt_module.malloc
        self.crt_malloc.restype = ctypes.c_void_p
        self.crt_malloc.argtypes = (ctypes.c_size_t,)
        
        self.crt_realloc = crt_module.realloc
        self.crt_realloc.restype = ctypes.c_void_p
        self.crt_realloc.argtypes = (ctypes.c_void_p, ctypes.c_size_t)

        self.crt_free = crt_module.free
        self.crt_free.argtypes = (ctypes.c_void_p,)

        # HERE'S THE PART WHERE CTYPES MAYBE KINDA HELPS
        self.crt_memset = ctypes.memset
        self.crt_memmove = ctypes.memmove
            
        self.address_map = dict()

    def allocate(self, byte_length):
        long = getattr(__builtin__, 'long', None)

        if long is None: # python3
            long = int
            
        if not isinstance(byte_length, (int, long)):
            raise AllocatorError('integer value not given')

        heap_buffer = ctypes.create_string_buffer(byte_length)
        heap_address = ctypes.addressof(heap_buffer)
        self.crt_memset(heap_address, 0, byte_length)
        
        allocation = Allocation(address=heap_address
                                ,buffer=heap_buffer
                                ,size=byte_length
                                ,allocator=self)
        
        self.address_map[heap_address] = allocation

        return allocation

    def allocate_string(self, string, encoding='ascii'):
        unicode = getattr(__builtin__, 'unicode', None)

        if unicode is None: # python 3
            unicode = str
            
        if not isinstance(string, (str, unicode)):
            raise AllocatorError('string value not given')

        try:
            string = bytes(string)
        except TypeError: # python3
            string = bytes(string, encoding)
            
        c_string = ctypes.create_string_buffer(string)
        c_address = ctypes.addressof(c_string)
        allocation = self.allocate(len(string)+1)
        ctypes.memset(allocation.address, 0, allocation.size) 
        ctypes.memmove(allocation.address, c_address, allocation.size-1)

        return allocation

    def reallocate(self, address, size):
        long = getattr(__builtin__, 'long', None)

        if long is None: # python 3
            long = int
        
        if not isinstance(address, (int, long)):
            raise AllocatorError('integer value not given for address')

        if address not in self.address_map:
            raise AllocatorError('no such address allocated: 0x%x' % address)

        allocation = self.address_map[address]
        new_buffer = ctypes.create_string_buffer(size)
        new_address = ctypes.addressof(new_buffer)
        
        self.crt_memset(new_address, 0, size)
        self.crt_memmove(new_address, allocation.address, allocation.size)

        allocation.address = new_address
        del allocation.buffer
        allocation.buffer = new_buffer

        allocation.size = size

        del self.address_map[address]
        self.address_map[new_address] = allocation

        return allocation

    def free(self, address):
        if address not in self.address_map:
            raise AllocatorError('no such address allocated: 0x%x' % address)

        allocation = self.address_map[address]
        allocation.address = 0
        allocation.size = 0
        del allocation.buffer
        allocation.buffer = None
        
        del self.address_map[address]

    def __del__(self):
        for address in list(self.address_map.keys()):
            self.free(address)

class Allocation(paranoia_agent.ParanoiaAgent):
    ADDRESS = None
    BUFFER = None
    SIZE = None
    ALLOCATOR = None
    
    def __init__(self, **kwargs):
        long = getattr(__builtin__, 'long', None)

        if long is None: # python 3
            long = int
            
        self.address = kwargs.setdefault('address', self.ADDRESS)
        self.buffer = kwargs.setdefault('buffer', self.BUFFER)
        self.size = kwargs.setdefault('size', self.SIZE)
        self.allocator = kwargs.setdefault('allocator', self.ALLOCATOR)

        if self.address is None:
            raise AllocationError('address cannot be None')
        if self.size is None:
            raise AllocationError('size cannot be None')
        if self.allocator is None:
            raise AllocationError('allocator cannot be None')

        if not isinstance(self.address, (int, long)):
            raise AllocationError('address must be an integer')
        if not isinstance(self.size, (int, long)):
            raise AllocationError('size must be an integer')
        if not isinstance(self.allocator, Allocator):
            raise AllocationError('allocator must be an Allocator instance')

    def is_null(self):
        return self.address == 0
    
    def check_address(self):
        if self.is_null():
            raise AllocationError('address is null')

    def address_object(self, offset=0):
        return address.Address(offset=offset, allocation=self)

    def reallocate(self, size):
        self.check_address()
        self.allocator.reallocate(self.address, size)

    def free(self):
        if self.is_null():
            return
        
        self.allocator.free(self.address)

    def read_bytestring(self, size=None, offset=0):
        self.check_address()
        
        if size is None:
            size = self.size

        if size+offset > self.size:
            raise AllocationError('size exceeds allocation size')

        address_read = ctypes.string_at(self.address+offset, size)
        return bytearray(address_read)

    def read_string(self, size=None, offset=0, encoding='ascii'):
        return self.read_bytestring(size, offset).decode(encoding)

    def read_bytes(self, size=None, offset=0):
        self.check_address()
        
        if size is None:
            size = self.size

        if size > self.size:
            raise AllocationError('size exceeds allocation size')

        return list(map(ord, self.read_string(size)))

    def write_bytestring(self, string, byte_offset=0):
        self.check_address()
        
        if not isinstance(string, (bytes, bytearray)):
            raise AllocationError('string or byte array value not given')

        if len(string)+byte_offset > self.size:
            raise AllocationError('string would overflow allocation')

        string_bytes = bytes(string)
        string_buffer = ctypes.create_string_buffer(string_bytes)
        string_address = ctypes.addressof(string_buffer)
        self.allocator.crt_memmove(self.address+byte_offset, string_address, len(string_bytes))

    def write_string(self, string, byte_offset=0, encoding='ascii'):
        self.write_bytestring(bytearray(string, encoding), byte_offset)

    def write_bytes(self, byte_list, byte_offset=0):
        self.check_address()
        
        if not getattr(byte_list, '__iter__', None):
            raise AllocationError('byte_list not iterable')

        return self.write_bytestring(bytearray(byte_list), byte_offset)
    
    def __del__(self):
        self.free()
