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
from paranoia.base import memory
from paranoia.converters import align, string_address

__all__ = ['AllocatorError', 'AllocationError', 'Allocator', 'Allocation']

class AllocatorError(paranoia_agent.ParanoiaError):
    pass

class AllocationError(paranoia_agent.ParanoiaError):
    pass

allocators = set()

class Allocator(paranoia_agent.ParanoiaAgent):
    def __init__(self, **kwargs):
        global allocators

        self.allocations = dict()

        allocators.insert(self)

    def allocate(self, length):
        raise AllocatorError('allocate not implemented')

    def reallocate(self, address, length):
        raise AllocatorError('reallocate not implemented')

    def free(self, address):
        if not address in self.allocations:
            raise AllocatorError('no such address %x' % address)

        self.allocations[address].invalidate()
        del self.allocations[address]

    def find(self, address):
        keys = filter(lambda x: x <= address < x+self.allocations[x].size
                      ,self.allocations.keys())

        if not len(keys):
            return None

        return self.allocations[address]

    def __del__(self):
        global allocators

        allocators.remove(self)

    @staticmethod
    def find_all(address):
        global allocators

        for allocator in allocators:
            allocation = allocator.find(address)

            if not allocation is None:
                return allocation

class MemoryAllocator(Allocator):
    def allocate(self, address):
        current = self.find(address)

        if not current is None:
            return current

        self.allocations[address] = Allocation(id=address, size=0, allocator=self)

        return self.allocations[address]
        

class HeapAllocator(paranoia_agent.ParanoiaAgent):
    ZERO_MEMORY = True
    
    def __init__(self, **kwargs):
        self.zero_memory = kwargs.setdefault('zero_memory', self.ZERO_MEMORY)
        self.allocations = dict()

    def allocate(self, byte_length):
        long = getattr(__builtin__, 'long', None)

        if long is None: # python3
            long = int
            
        if not isinstance(byte_length, (int, long)):
            raise AllocatorError('integer value not given')

        heap_address = memory.malloc(byte_length)

        if self.zero_memory:
            memory.memset(heap_address, 0, byte_length)
        
        allocation = Allocation(id=heap_address
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

        if self.zero_memory:
            memory.memset(allocation.address, 0, allocation.size)
            
        memory.memmove(allocation.address, c_address, allocation.size-1)

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
        new_address = memory.realloc(address, size)

        allocation.id = new_address

        if size - allocation.size > 0 and self.zero_memory:
            delta = size - allocation.size
            memory.memset(new_address+allocation.size, 0, delta)
            
        allocation.size = size

        del self.address_map[address]
        self.address_map[new_address] = allocation
        
        return allocation

    def free(self, address):
        if address not in self.address_map:
            raise AllocatorError('no such address allocated: 0x%x' % address)

        allocation = self.address_map[address]

        memory.memset(address, 0, allocation.size)
        memory.free(address)
        allocation.address = 0
        allocation.size = 0
        
        del self.address_map[address]

    def __del__(self):
        for address in self.address_map:
            self.free(address)

GLOBAL_ALLOCATOR = Allocator()

class Allocation(paranoia_agent.ParanoiaAgent):
    ID = None
    SIZE = None
    ALLOCATOR = None
    
    def __init__(self, **kwargs):
        long = getattr(__builtin__, 'long', None)

        if long is None: # python 3
            long = int
            
        self.id = kwargs.setdefault('id', self.ID)
        self.size = kwargs.setdefault('size', self.SIZE)
        self.allocator = kwargs.setdefault('allocator', self.ALLOCATOR)

        if self.id is None:
            raise AllocationError('id cannot be None')
        if self.size is None:
            raise AllocationError('size cannot be None')
        if self.allocator is None:
            raise AllocationError('allocator cannot be None')

        if not isinstance(self.id, (int, long)):
            raise AllocationError('id must be an integer')
        if not isinstance(self.size, (int, long)):
            raise AllocationError('size must be an integer')
        if not isinstance(self.allocator, Allocator):
            raise AllocationError('allocator must be an Allocator instance')

    def is_null(self):
        return self.id == 0
    
    def in_range(self, other_id):
        return self.id <= other_id < self.id+self.size

    def check_id(self):
        if self.is_null():
            raise AllocationError('id is null')

    def check_id_range(self, other_id):
        if not self.in_range(other_id):
            raise AllocationError('id out of range')

    def address_object(self, offset=0):
        return address.Address(offset=offset, allocation=self)

    def reallocate(self, size):
        self.check_id()
        self.allocator.reallocate(self.id, size)

    def free(self):
        if self.is_null():
            return
        
        self.allocator.free(self.id)

    def read_bytestring(self, id_val, size=None, offset=0):
        self.check_id_range(id_val)
        
        if size is None:
            size = self.size

        if size+offset > self.size:
            raise AllocationError('size exceeds allocation size')

        address_read = ctypes.string_at(id_val, size)
        return bytearray(address_read)

    def read_string(self, id_val, size=None, offset=0, encoding='ascii'):
        return self.read_bytestring(id_val, size, offset).decode(encoding)

    def read_bytes(self, id_val, size=None, offset=0):
        bytelist = list(self.read_bytestring(id_val, size, offset))

        if len(bytelist) == 0:
            return bytelist

        if not isinstance(bytelist[0], int):
            return map(ord, bytelist)

        return bytelist

    def write_bytestring(self, id_val, string, byte_offset=0):
        self.check_id_range(id_val)

        if len(string)+byte_offset > self.size:
            raise AllocationError('write exceeds allocation size')
        
        if not isinstance(string, (bytes, bytearray)):
            raise AllocationError('string or byte array value not given')

        string_bytes = bytes(string)
        string_buffer = ctypes.create_string_buffer(string_bytes)
        string_address = ctypes.addressof(string_buffer)

        memory.memmove(id_val, string_address, len(string_bytes))

    def write_string(self, string, byte_offset=0, encoding='ascii'):
        self.write_bytestring(bytearray(string, encoding), byte_offset)

    def write_bytes(self, byte_list, byte_offset=0):
        return self.write_bytestring(bytearray(byte_list), byte_offset)

    def __del__(self):
        self.free()
