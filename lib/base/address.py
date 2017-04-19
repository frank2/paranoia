#!/usr/bin/env python

try:
    import __builtin__
except ImportError: # python3
    import builtins as __builtin__

from paranoia.base.paranoia_agent import ParanoiaAgent, ParanoiaError

__all__ = ['AddressError', 'Address']

class AddressError(ParanoiaError):
    pass

class Address(ParanoiaAgent):
    ALLOCATION = None
    OFFSET = 0

    def __init__(self, **kwargs):
        from paranoia.base.allocator import Allocation
        
        long = getattr(__builtin__, 'long', None)

        if long is None: # python 3
            long = int
            
        self.allocation = kwargs.setdefault('allocation', self.ALLOCATION)

        if not self.allocation is None and not isinstance(self.allocation, Allocation):
            raise AddressError('allocation must be an Allocation object')
        
        self.offset = kwargs.setdefault('offset', self.OFFSET)

        if not isinstance(self.offset, (int, long)):
            raise AddressError('offset must be an int or a long')

        self.set_offset(self.offset)

    def value(self):
        if self.allocation is None:
            raise AddressError('address is invalid')
        
        return self.allocation.id + self.offset

    def set_offset(self, value):
        from paranoia.base.allocator import memory, Allocator
        
        if self.allocation is None:
            # if there's no allocation, we assume this address is just an abstract memory pointer. find its
            # allocation in memory and, if it doesn't exist, create it

            self.allocation = Allocator.find_all(self.offset)

            if not self.allocation is None:
                self.offset = self.offset - self.allocation.id
            else:
                # we're sort of reverse-allocating an address, so this is gonna look weird
                self.allocation = memory.allocate(self.offset)
                self.allocation.addresses[0] = self
                self.offset = 0
        else:
            self.offset = value

    def fork(self, offset):
        self.allocation.check_id_range(int(self)+offset)
        
        return self.allocation.address(self.offset+offset)

    def copy(self):
        return self.__class__(offset=self.offset, allocation=self.allocation)

    def get_block(self, offset=0, force=False):
        return self.allocation.get_block(int(self)+offset, force)

    def set_block(self, block, offset=0, force=False):
        return self.allocation.set_block(int(self)+offset, block, force)

    def read_byte(self, offset=0):
        return self.allocation.read_byte(int(self)+offset)

    def write_byte(self, value, offset=0):
        return self.allocation.write_byte(int(self)+offset, value)

    def read_bytestring(self, offset=0, size=None, force=False, direct=False):
        return self.allocation.read_bytestring(int(self)+offset, size, force, direct)

    def read_string(self, offset=0, size=None, encoding='ascii', force=False, direct=False):
        return self.allocation.read_string(int(self)+offset, size, encoding, force, direct)

    def read_bytes(self, offset=0, size=None, force=False, direct=False):
        return self.allocation.read_bytes(int(self)+offset, size, force, direct)

    def read_bits(self, bit_offset=0, size=None, force=False, direct=False):
        return self.allocation.read_bits(int(self)+bit_offset/8, bit_offset % 8, size, force, direct)

    def write_bytestring(self, string, offset=0, force=False, direct=False):
        return self.allocation.write_bytestring(int(self)+offset, string, force, direct)

    def write_string(self, string, offset=0, encoding='ascii', force=False, direct=False):
        return self.allocation.write_string(int(self)+offset, string, encoding, force, direct)

    def write_bytes(self, byte_list, offset=0, force=False, direct=False):
        return self.allocation.write_bytes(int(self)+offset, byte_list, force, direct)

    def write_bits(self, bit_list, bit_offset=0, force=False, direct=False):
        return self.allocation.write_bits(int(self)+bit_offset/8, bit_list, bit_offset % 8, force, direct)

    def flush(self, offset=0, size=None):
        self.allocation.flush(id_val=int(self)+offset, size=size)

    def __int__(self):
        return self.value()

    def __repr__(self):
        return '<Address:0x%X>' % (int(self))

    def __hash__(self):
        return hash(int(self))
