#!/usr/bin/env python

import ctypes

from paranoia.base import paranoia_agent, memory

try:
    import __builtin__
except ImportError: # python3
    import builtins as __builtin__

__all__ = ['AddressError', 'Address']

class AddressError(paranoia_agent.ParanoiaError):
    pass

class Address(paranoia_agent.ParanoiaAgent):
    ALLOCATION = None
    OFFSET = 0

    def __init__(self, **kwargs):
        long = getattr(__builtin__, 'long', None)

        if long is None: # python 3
            long = int
            
        self.allocation = kwargs.setdefault('allocation', self.ALLOCATION)
        self.offset = kwargs.setdefault('offset', self.OFFSET)

        if not isinstance(self.offset, (int, long)):
            raise AddressError('offset must be an int or a long')

        self.set_offset(self.offset)

    def is_bound(self):
        return not self.allocation is None

    def value(self):
        if self.is_bound():
            return self.allocation.id + self.offset

        return self.offset

    def set_offset(self, value):
        self.offset = value

        if self.allocation:
            self.allocation.check_id_range(int(self))

    def fork(self, offset):
        return Address(offset=self.offset+offset, allocation=self.allocation)

    def read_bytestring(self, size=None, offset=0):
        target = int(self)+offset
        
        if self.is_bound():
            return self.allocation.read_bytestring(target, size, offset)

        if size is None:
            raise AllocationError('size cannot be None when address has no allocation')

        address_read = ctypes.string_at(target, size)
        return bytearray(address_read)

    def read_string(self, size=None, offset=0, encoding='ascii'):
        return self.read_bytestring(size, offset).decode(encoding)

    def read_bytes(self, size=None, offset=0):
        bytelist = list(self.read_bytestring(size, offset))

        if len(bytelist) == 0:
            return bytelist

        if not isinstance(bytelist[0], int):
            return map(ord, bytelist)

        return bytelist

    def write_bytestring(self, string, byte_offset=0):
        target = int(self)+byte_offset

        if self.is_bound():
            return self.allocation.write_bytestring(target, string, byte_offset)
        
        if not isinstance(string, (bytes, bytearray)):
            raise AllocationError('string or byte array value not given')

        string_bytes = bytes(string)
        string_buffer = ctypes.create_string_buffer(string_bytes)
        string_address = ctypes.addressof(string_buffer)
        
        memory.memmove(target, string_address, len(string_bytes))

    def write_string(self, string, byte_offset=0, encoding='ascii'):
        self.write_bytestring(bytearray(string, encoding), byte_offset)

    def write_bytes(self, byte_list, byte_offset=0):
        return self.write_bytestring(bytearray(byte_list), byte_offset)

    def __int__(self):
        return self.value()

    def __repr__(self):
        return '<Address:%X>' % (int(self))
