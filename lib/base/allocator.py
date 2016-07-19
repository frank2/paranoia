#!/usr/bin/env python

import platform
import ctypes
import traceback

from paranoia.base import paranoia_agent
from paranoia.base import address
from paranoia.converters import string_address

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
        elif system == 'Linux' or system.startswith('CYGWIN'):
            crt_module = ctypes.cdll.LoadLibrary('libc.so.6')
        elif system == 'Darwin':
            crt_module = ctypes.cdll.LoadLibrary('libc.dylib')
        else:
            AllocatorError('unsupported platform %s' % system)

        self.crt_malloc = crt_module.malloc
        self.crt_realloc = crt_module.realloc
        self.crt_free = crt_module.free
        self.crt_memset = crt_module.memset
        self.crt_memmove = ctypes.memmove
        # do not import the crt version of memmove... for some reason it segfaults
            
        self.address_map = dict()

    def allocate(self, byte_length):
        if not isinstance(byte_length, (int, long)):
            raise AllocatorError('integer value not given')

        heap_address = self.crt_malloc(byte_length)
        self.crt_memset(heap_address, 0, byte_length)
        
        allocation = Allocation(address=heap_address, size=byte_length, allocator=self)
        self.address_map[heap_address] = allocation

        return allocation

    def allocate_string(self, string):
        if not isinstance(string, basestring):
            raise AllocatorError('string value not given')

        c_string = ctypes.create_string_buffer(string)
        c_address = ctypes.addressof(c_string)
        allocation = self.allocate(len(string)+1)
        ctypes.memmove(allocation.address, c_address, len(string))

        return allocation

    def reallocate(self, address, size):
        if not isinstance(address, (int, long)):
            raise AllocatorError('integer value not given for address')

        if not isinstance(address, (int, long)):
            raise AllocatorError('integer value not given for address')

        if not self.address_map.has_key(address):
            raise AllocatorError('no such address allocated: 0x%x' % address)

        allocation = self.address_map[address]

        new_address = self.crt_realloc(address, size)
        del self.address_map[address]
        self.address_map[new_address] = allocation
        
        allocation.address = new_address
        allocation.size = size

        return allocation

    def free(self, address):
        if not self.address_map.has_key(address):
            raise AllocatorError('no such address allocated: 0x%x' % address)

        self.crt_free(address)
        allocation = self.address_map[address]
        allocation.address = 0
        allocation.size = 0
        del self.address_map[address]

    def __del__(self):
        for address in self.address_map.keys():
            self.free(address)

class Allocation(paranoia_agent.ParanoiaAgent):
    ADDRESS = None
    SIZE = None
    ALLOCATOR = None
    
    def __init__(self, **kwargs):
        self.address = kwargs.setdefault('address', self.ADDRESS)
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

    def read_string(self, size=None, offset=0):
        self.check_address()
        
        if size is None:
            size = self.size

        if size+offset > self.size:
            raise AllocationError('size exceeds allocation size')
            
        return ctypes.string_at(self.address+offset, size)

    def read_bytes(self, size=None):
        self.check_address()
        
        if size is None:
            size = self.size

        if size > self.size:
            raise AllocationError('size exceeds allocation size')

        return map(ord, self.read_string(size))

    def write_string(self, string, byte_offset=0):
        self.check_address()
        
        if not isinstance(string, basestring):
            raise AllocationError('string value not given')

        if len(string)+byte_offset > self.size:
            raise AllocationError('string would overflow allocation')

        self.allocator.crt_memmove(self.address+byte_offset, string_address(string), len(string))

    def write_bytes(self, byte_list):
        self.check_address()
        
        if not getattr(byte_list, '__iter__', None):
            raise AllocationError('byte_list not iterable')

        return self.write_string(''.join(map(chr, byte_list)))

    def __del__(self):
        self.free()
