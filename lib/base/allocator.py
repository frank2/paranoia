#!/usr/bin/env python

import platform
import ctypes
import os
import random
import sys
import traceback

try:
    import __builtin__
except ImportError: # python3
    import builtins as __builtin__

from yggdrasil import AVLTree

from paranoia.fundamentals import align, string_address, malloc, realloc, free, hexdump
from paranoia.fundamentals import memset, memmove
from paranoia.base.address import Address, AddressError
from paranoia.base.block import Block, BlockChain
from paranoia.base.paranoia_agent import ParanoiaAgent, ParanoiaError

allocators = set()
memory = None
heap = None

__all__ = ['AllocatorError', 'AllocationError', 'Allocator', 'Allocation'
           ,'MemoryAllocator', 'HeapAllocator', 'MemoryAllocation', 'VirtualAllocation'
           ,'VirtualAllocator', 'VirtualAddress', 'heap', 'memory', 'allocators']

class AllocatorError(ParanoiaError):
    pass

class AllocationError(ParanoiaError):
    pass

class Allocation(ParanoiaAgent):
    ID = None
    SIZE = None
    ALLOCATOR = None
    BUFFER = True
    
    def __init__(self, **kwargs):
        long = getattr(__builtin__, 'long', None)

        if long is None: # python 3
            long = int
            
        self.id = kwargs.setdefault('id', self.ID)
        self.size = kwargs.setdefault('size', self.SIZE)
        self.allocator = kwargs.setdefault('allocator', self.ALLOCATOR)
        self.buffer = kwargs.setdefault('buffer', self.BUFFER)

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

        self.addresses = dict()
        self.blocks = dict()

    def hexdump(self, label=None):
        self.check_id()
        
        hexdump(self.id, self.size, label)

    def set_buffering(self, buffering):
        if not isinstance(buffering, bool):
            raise AllocationError('buffering should be a boolean')

        self.buffer = buffering

        for block_id in self.blocks:
            self.blocks[block_id].buffer = self.buffer

    def is_null(self):
        return self.id == 0
    
    def in_range(self, other_id, inclusive=False):
        if inclusive:
            return self.id <= other_id <= self.id+self.size
        else:
            return self.id <= other_id < self.id+self.size

    def check_id(self):
        if self.is_null():
            raise AllocationError('id is null')

    def check_id_range(self, other_id, inclusive=False):
        if not self.in_range(other_id, inclusive):
            raise AllocationError('id out of range')

    def address(self, offset=0):
        if offset > self.size:
            raise AllocationError('address out of range')
        
        if not offset in self.addresses:
            self.addresses[offset] = Address(offset=offset, allocation=self)
            
        return self.addresses[offset]

    def reallocate(self, size):
        self.check_id()
        self.allocator.reallocate(self.id, size)

    def free(self):
        if self.is_null():
            return

        self.allocator.free(self.id)
        self.id = 0

    def get_block(self, id_val, force=False):
        self.check_id()
        self.check_id_range(id_val)
        
        delta = id_val - self.id

        if not delta in self.blocks:
            self.set_block(id_val, Block(address=self.address(delta), buffer=self.buffer), force)

        return self.blocks[delta]

    def set_block(self, id_val, block, force=False):
        self.check_id()
        self.check_id_range(id_val)

        if not isinstance(block, Block):
            raise AllocationError('block must be a Block object')

        delta = id_val - self.id

        if delta in self.blocks:
            self.blocks[delta].set_value(block.get_value(force))
        else:
            block.buffer = self.buffer
            block.address = self.address(delta)
            self.blocks[delta] = block

        if not block.value is None and (self.buffer or force):
            self.flush(id_val, 1)

    def read_byte(self, id_val):
        self.check_id()
        self.check_id_range(id_val)

        byte = ctypes.string_at(id_val, 1)

        return ord(byte)

    def write_byte(self, id_val, byte_val):
        self.check_id()
        self.check_id_range(id_val)

        if not 0 <= byte_val < 256:
            raise AllocationError('byte_val must be 0 <= byte_val < 256')

        str_val = chr(byte_val)
        str_addr = string_address(str_val)
        memmove(id_val, str_addr, 1)

    def read_bytestring(self, id_val, size=None, force=False, direct=False):
        self.check_id()
        self.check_id_range(id_val)

        offset = id_val - self.id
        
        if size is None:
            size = self.size - offset

        if size < 0:
            raise AllocationError('size is negative')

        if size+offset > self.size:
            raise AllocationError('size exceeds allocation size')

        data_read = bytes(ctypes.string_at(self.id+offset, size))

        if self.buffer and not direct:
            affected_blocks = filter(lambda x: offset <= x < size+offset, self.blocks.keys())
            
            for block_id in affected_blocks:
                block = self.blocks[block_id]
                value = data_read[block_id]

                if isinstance(value, int):
                    block.value = value
                else:
                    block.value = ord(value)

        return data_read

    def read_string(self, id_val, size=None, encoding='ascii', force=False, direct=False):
        return self.read_bytestring(id_val, size, force, direct).decode(encoding)

    def read_bytes(self, id_val, size=None, force=False, direct=False):
        bytelist = list(self.read_bytestring(id_val, size, force, direct))

        if len(bytelist) == 0:
            return bytelist

        if not isinstance(bytelist[0], int):
            return map(ord, bytelist)

        return bytelist

    def read_bits(self, id_val, bit_offset=0, size=None, force=False, direct=False):
        if size is None:
            size = self.size * 8 - bit_offset
            
        bytelist = self.read_bytes(id_val, align(bit_offset+size, 8), force, direct)
        bitlist = list()

        for byte in bytelist:
            for i in reversed(xrange(8)):
                bitlist.append((byte >> i) & 1)

        return bitlist[bit_offset:bit_offset+size]
                                       
    def write_bytestring(self, id_val, string, force=False, direct=False):
        self.check_id()
        self.check_id_range(id_val)

        offset = id_val - self.id

        if len(string)+offset > self.size:
            raise AllocationError('write exceeds allocation size')
        
        if not isinstance(string, (bytes, bytearray)):
            raise AllocationError('byte array not given')

        long = getattr(__builtin__, 'long', None)

        if not long is None: # python 2
            string_buffer = ctypes.create_string_buffer(str(string))
        else:
            string_buffer = ctypes.create_string_buffer(string)
            
        string_address = ctypes.addressof(string_buffer)
        memmove(id_val, string_address, len(string))

        if self.buffer and not direct:
            affected_blocks = filter(lambda x: offset <= x < len(string)+offset, self.blocks.keys())
            
            for block_id in affected_blocks:
                block = self.blocks[block_id]
                block.value = None

    def write_string(self, id_val, string, encoding='ascii', force=False, direct=False):
        self.write_bytestring(id_val, bytearray(string, encoding), force, direct)

    def write_bytes(self, id_val, byte_list, force=False, direct=False):
        return self.write_bytestring(id_val, bytearray(byte_list), force, direct)

    def write_bits(self, id_val, bit_list, bit_offset=0, force=False, direct=False):
        shifted_length = bit_offset + len(bit_list)
        padding_front = list()
        front_block = self.get_block(id_val)

        for i in xrange(bit_offset):
            padding_front.append(front_block.get_bit(i, force))
            
        padding_back = list()
        back_addr = id_val + align(shifted_length, 8)/8 - 1
        back_block = self.get_block(back_addr)
        active_bits = shifted_length % 8
        back_size = 8 * int(not active_bits == 0) - active_bits

        for i in xrange(back_size):
            padding_back.append(back_block.get_bit(i + active_bits, force))

        bit_list = padding_front + bit_list + padding_back
        bytelist = list()

        for i in xrange(len(bit_list)/8):
            value = 0

            for j in xrange(8):
                value <<= 1
                value |= bit_list[i*8+j]

            bytelist.append(value)

        self.write_bytes(id_val, bytelist, force, direct)

    def flush(self, id_val=None, size=None):
        if not self.buffer:
            # everything is technically flushed, skip
            return
        
        if size is None:
            size = self.size

        if size == 0:
            return

        if id_val is None:
            id_val = self.id

        self.check_id_range(id_val)

        start_delta = id_val - self.id

        if size == self.size and not start_delta == 0:
            end_delta = size - start_delta
        else:
            end_delta = start_delta + size

        block_range = list()

        if size == 1:
            block = self.get_block(id_val)

            if not block.value is None:
                block.flush()
                
            return

        for i in range(start_delta, end_delta+1):
            if not i == end_delta and i in self.blocks and not self.blocks[i].value is None and len(block_range) == 0:
                block_range.append(i)
            elif i == end_delta or (not i in self.blocks or self.blocks[i].value is None) and len(block_range) == 1:
                if len(block_range) == 0: # end of data
                    break
                
                block_range.append(i)

                block_start, block_end = block_range
                byte_array = bytearray(map(lambda x: self.blocks[x].value, range(*block_range)))
                
                long = getattr(__builtin__, 'long', None)

                if not long is None: # python 2
                    string_buffer = ctypes.create_string_buffer(str(byte_array))
                else:
                    string_buffer = ctypes.create_string_buffer(byte_array)

                string_address = ctypes.addressof(string_buffer)

                memmove(self.id+block_start, string_address, len(byte_array))

                for i in range(*block_range):
                    self.blocks[i].value = None

                block_range = list()

    def invalidate(self):
        for address_index in self.addresses:
            self.addresses[address_index].allocation = None

    def __len__(self):
        return self.size

    def __getitem__(self, index):
        if index < 0:
            index += self.size

        return self.get_block(self.id + index)

    def __setitem__(self, index, block_value):
        if not isinstance(block_value, Block):
            raise AllocationError('block_value not a Block instance')

        if index < 0:
            index += self.size

        self.set_block(self.id + index, block_value)

    def __del__(self):
        if self.id in self.allocator.allocations:
            self.free()

class Allocator(ParanoiaAgent):
    BUFFER = True
    ALLOCATION_CLASS = Allocation
    
    def __init__(self, **kwargs):
        global allocators

        self.buffer = kwargs.setdefault('buffer', self.BUFFER)
        self.allocations = AVLTree()
        self.allocation_class = kwargs.setdefault('allocation_class', self.ALLOCATION_CLASS)

        if not issubclass(self.allocation_class, Allocation):
            raise AllocatorError('allocation class must subclass Allocation')

        allocators.add(self)

    def set_buffering(self, buffering):
        if not isinstance(buffering, bool):
            raise AllocatorError('buffering must be a bool')

        self.buffer = buffering

        for allocation_id in self.allocations:
            self.allocations[allocation_id].value.set_buffering(self.buffer)

    def allocate(self, length):
        raise AllocatorError('allocate not implemented')

    def reallocate(self, address, length):
        raise AllocatorError('reallocate not implemented')

    def free(self, address):
        if not address in self.allocations:
            raise AllocatorError('no such address %x' % address)

        self.allocations[address].value.invalidate()
        del self.allocations[address]

    def find(self, address):
        if address in self.allocations:
            return self.allocations[address].value

        # root address not found, see if it's in a range
        node = self.allocations.root

        while not node is None:
            allocation = node.value

            if address >= allocation.id and address < allocation.id+allocation.size:
                return allocation

            branch = node.branch_function(address, node.label)

            if branch < 0:
                node = node.left
            elif branch > 0:
                node = node.right

    def __del__(self):
        global allocators

        if not allocators is None:
            allocators.remove(self)

        for address in self.allocations:
            self.free(address)

    @staticmethod
    def find_all(address):
        global allocators

        for allocator in allocators:
            allocation = allocator.find(address)

            if not allocation is None:
                return allocation

class MemoryAllocation(Allocation):
    def check_id_range(self, id_val):
        if id_val < self.id:
            raise AllocationError('id not in range')

        size_at = id_val - self.id + 1
        
        if size_at > self.size:
            self.reallocate(size_at)

        return super(MemoryAllocation, self).check_id_range(id_val)
    
    def read_bytestring(self, id_val, size=None, force=False, direct=False):
        if id_val < self.id:
            raise AllocationError('bad id value')

        delta = id_val - self.id

        if size is None:
            size = self.size - delta

        new_size = delta+size

        if new_size > self.size:
            self.reallocate(new_size)

        return super(MemoryAllocation, self).read_bytestring(id_val, size, force, direct)

    def write_bytestring(self, id_val, string, force=False, direct=False):
        if id_val < self.id:
            raise AllocationError('bad id value')

        delta = id_val - self.id
        size = len(string)
        new_size = delta+size

        if new_size > self.size:
            self.rellocate(new_size)

        return super(MemoryAllocation, self).write_bytestring(id_val, string, force, direct)

class MemoryAllocator(Allocator):
    ALLOCATION_CLASS = MemoryAllocation
    
    def allocate(self, address):
        current = self.find(address)

        if not current is None:
            raise AllocatorError('address already has allocation')

        self.allocations[address] = self.allocation_class(id=address, size=1, allocator=self, buffer=self.buffer)

        return self.allocations[address].value

    def reallocate(self, address, size):
        if not address in self.allocations:
            raise AllocatorError('address was not allocated by allocator')

        end_address = address+size
        allocation = self.allocations[address].value
        allocation.size = size

        consumed_allocations = filter(lambda x: not x == start_address and start_address <= x < end_address, self.allocations.keys())
        consumed_allocations.sort()

        for consumed_addr in consumed_allocations:
            self.consume_address(consumed_addr, start_address, end_address)

        return allocation
    
    def consume_address(self, consumed_address, start_address, end_address):
        if not consumed_address in self.allocations:
            raise AllocationError('consumed address not in allocations')

        if not consumed_address >= start_address or not consumed_address < end_address:
            raise AllocationError('consumed address not in the range of start and end')
        
        consumed_offset = consumed_address - start_address
        consumed_alloc = self.allocations[consumed_address].value
        consumed_size = consumed_alloc.size
        consumed_end = consumed_address + consumed_size
        consumed_offset_end = consumed_offset + consumed_size
        consumed_addresses = filter(lambda x: x+consumed_offset < size, consumed_alloc.addresses.keys())
            
        # shift and save the overlapped address objects
        for address_offset in consumed_addresses:
            address_obj = consumed_alloc.addresses[address_offset]
            address_obj.allocation = allocation
            address_obj.offset += consumed_offset
            allocation.addresses[consumed_offset+address_offset] = address_obj
            del consumed_alloc.addresses[address_offset]
                
        consumed_blocks = filter(lambda x: x+consumed_offset < size, consumed_alloc.blocks.keys())
            
        # save the overlapped blocks into our allocation
        for block_offset in consumed_blocks:
            block = consumed_alloc.blocks[block_offset]
            allocation.set_block(int(block.address), block, True)
            del consumed_alloc.blocks[block_offset]

        if consumed_end <= end_address:
            del self.allocations[consumed_addr]
            return
            
        # this region only overlaps partially, move the beginning of the consumed region
        # to the end of the new allocation
        unconsumed_addresses = filter(lambda x: x+consumed_offset >= size, consumed_alloc.addresses.keys())
        unconsumed_blocks = filter(lambda x: x+consumed_offset >= size, consumed_alloc.blocks.keys())
        unconsumed_delta = size - consumed_offset

        for unconsumed_offset in unconsumed_blocks:
            new_offset = unconsumed_offset - unconsumed_delta
            unconsumed_block = consumed_alloc.blocks[unconsumed_offset]
            consumed_alloc.blocks[new_offset] = unconsumed_block
            del consumed_alloc.blocks[unconsumed_offset]
                    
            unconsumed_block.address.allocation = consumed_alloc
            unconsumed_block.address.offset -= unconsumed_delta

        consumed_alloc.id = end_address

        del self.allocations[consumed_address]
        self.allocations[end_address] = consumed_alloc

memory = MemoryAllocator()

class HeapAllocator(Allocator):
    ZERO_MEMORY = True
                                       
    def __init__(self, **kwargs):
        Allocator.__init__(self, **kwargs)
        self.zero_memory = kwargs.setdefault('zero_memory', self.ZERO_MEMORY)

    def allocate(self, byte_length):
        long = getattr(__builtin__, 'long', None)

        if long is None: # python3
            long = int
            
        if not isinstance(byte_length, (int, long)):
            raise AllocatorError('integer value not given')

        heap_address = malloc(byte_length)

        if self.zero_memory:
            memset(heap_address, 0, byte_length)
        
        allocation = self.allocation_class(id=heap_address
                                           ,size=byte_length
                                           ,allocator=self)

        self.allocations[heap_address] = allocation

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
            memset(allocation.address, 0, allocation.size)
            
        memmove(allocation.address, c_address, allocation.size-1)

        return allocation

    def reallocate(self, address, size):
        long = getattr(__builtin__, 'long', None)

        if long is None: # python 3
            long = int
        
        if not isinstance(address, (int, long)):
            raise AllocatorError('integer value not given for address')

        if not address in self.allocations:
            raise AllocatorError('no such address allocated: 0x%x' % address)

        allocation = self.allocations[address].value
        new_address = realloc(address, size)

        allocation.id = new_address

        if size - allocation.size > 0 and self.zero_memory:
            delta = size - allocation.size
            memset(new_address+allocation.size, 0, delta)
            
        allocation.size = size

        del self.allocations[address]
        self.allocations[new_address] = allocation
        
        return allocation

    def free(self, address):
        if address not in self.allocations:
            raise AllocatorError('no such address allocated: 0x%x' % address)

        allocation = self.allocations[address].value

        memset(address, 0, allocation.size)
        free(address)
        allocation.address = 0
        allocation.size = 0

        del self.allocations[address]

heap = HeapAllocator()
BlockChain.ALLOCATOR = heap

class VirtualAddressError(AddressError):
    pass

class VirtualAddress(Address):
    ALLOCATOR = None
    
    def __init__(self, **kwargs):
        super(VirtualAddress, self).__init__(**kwargs)

        self.allocator = kwargs.setdefault('allocator', self.ALLOCATOR)
        
        if self.allocation is None and self.allocator is None:
            raise VirtualAddressError('both the allocation and the allocator cannot be None')

        if not self.allocator is None and not isinstance(self.allocator, VirtualAllocator):
            raise VirtualAddressError('allocator must be a VirtualAllocator instance')

    def reverse_allocate(self, size):
        if self.allocator is None:
            raise VirtualAddressError('allocator cannot be None for reverse allocation')
        
        if not self.allocation is None:
            del self.allocation.addresses[self.offset]

        self.allocation = self.allocator.allocate(self.offset, size)
        self.allocation.addresses[self.offset] = self

    def ensure_allocation(self, offset=None, size=None):
        if offset is None:
            offset = self.offset
        else:
            offset = self.offset+offset
            
        if size is None:
            if not self.allocation is None:
                size = self.allocation.size - offset
            elif not self.allocator is None:
                size = self.allocator.maximum_offset - offset
            else:
                raise VirtualAddressError('allocator and allocation cannot be None')

        if self.allocation is None:
            self.reverse_allocate(size)
        elif offset+size >= self.allocation.size:
            self.allocation.reallocate(offset+size)

    def valid(self, inclusive=False):
        if not self.allocation is None:
            return self.allocation.in_range(int(self), inclusive)
        elif not self.allocator is None:
            return self.allocator.in_range(int(self), inclusive)
        else:
            return False

    def fork(self, offset):
        if not self.allocation is None:
            return self.allocation.address(self.offset+offset)
        elif not self.allocator is None:
            return self.allocator.address(self.offset+offset)
        else:
            raise VirtualAddressError('cannot fork with no allocation or allocator')

    def copy(self):
        return self.__class__(offset=self.offset
                              ,allocation=self.allocation
                              ,allocator=self.allocator)

    def get_block(self, offset=0, force=False):
        self.ensure_allocation(offset, 1)
        return super(VirtualAddress, self).get_block(offset, force)

    def set_block(self, block, offset=0, force=False):
        self.ensure_allocation(offset, 1)
        return super(VirtualAddress, self).set_block(block, offset, force)

    def read_byte(self, offset=0):
        self.ensure_allocation(offset, 1)
        return super(VirtualAddress, self).read_byte(offset)

    def write_byte(self, value, offset=0):
        self.ensure_allocation(offset, 1)
        return super(VirtualAddress, self).write_byte(value, offset)

    def read_bytestring(self, offset=0, size=None, force=False, direct=False):
        self.ensure_allocation(offset, size)
        return super(VirtualAddress, self).read_bytestring(offset, size, force, direct)

    def read_string(self, offset=0, size=None, encoding='ascii', force=False, direct=False):
        self.ensure_allocation(offset, size)
        return super(VirtualAddress, self).read_string(offset, size, encoding, force, direct)

    def read_bytes(self, offset=0, size=None, force=False, direct=False):
        self.ensure_allocation(offset, size)
        return super(VirtualAddress, self).read_bytes(offset, size, force, direct)

    def read_bits(self, bit_offset=0, size=None, force=False, direct=False):
        self.ensure_allocation(bit_offset/8, size)
        return super(VirtualAddress, self).read_bits(bit_offset, size, force, direct)

    def write_bytestring(self, string, offset=0, force=False, direct=False):
        self.ensure_allocation(offset, len(string))
        return super(VirtualAddress, self).write_bytestring(string, offset, force, direct)

    def write_string(self, string, offset=0, encoding='ascii', force=False, direct=False):
        self.ensure_allocation(offset, len(string))
        return super(VirtualAddress, self).write_string(string, offset, encoding, force, direct)

    def write_bytes(self, byte_list, offset=0, force=False, direct=False):
        self.ensure_allocation(offset, len(byte_list))
        return super(VirtualAddress, self).read_bytes(byte_list, offset, force, direct)

    def write_bits(self, bit_list, bit_offset=0, size=None, force=False, direct=False):
        self.ensure_allocation(bit_offset/8, Size(size=bit_offset % 8 + len(bit_list)).byte_length())
        return super(VirtualAddress, self).write_bits(bit_list, bit_offset, force, direct)

class VirtualAllocation(Allocation):
    def address(self, offset=0):
        if offset >= self.size:
            return self.allocator.address(offset)

        if not offset in self.addresses:
            self.addresses[offset] = VirtualAddress(offset=offset
                                                    ,allocation=self
                                                    ,allocator=self.allocator)

        return self.addresses[offset]
    
    def hexdump(self, label=None):
        self.check_id()
        
        backing_alloc = self.allocator.backing_allocations[self.id]

        if not label:
            label = '<Virtual:%X>' % self.id

        backing_alloc.hexdump(label)

    def get_block(self, id_val, force=False):
        self.check_id()
        self.check_id_range(id_val)

        mem_addr = self.allocator.memory_address(id_val)
        backing_alloc = self.allocator.backing_allocations[self.id]
        return backing_alloc.get_block(mem_addr)

    def set_block(self, id_val, block, force=False):
        self.check_id()
        self.check_id_range(id_val)

        mem_addr = self.allocator.memory_address(id_val)
        backing_alloc = self.allocator.backing_allocations[self.id]
        return backing_alloc.set_block(mem_addr, block, force)
        
    def read_byte(self, id_val):
        self.check_id()
        self.check_id_range(id_val)

        mem_addr = self.allocator.memory_address(id_val)
        backing_alloc = self.allocator.backing_allocations[self.id]
        return backing_alloc.read_byte(mem_addr)
    
    def write_byte(self, id_val, byte_val):
        self.check_id()
        self.check_id_range(id_val)

        mem_addr = self.allocator.memory_address(id_val)
        backing_alloc = self.allocator.backing_allocations[self.id]
        return backing_alloc.write_byte(mem_addr, byte_val)

    def read_bytestring(self, id_val, size=None, force=False, direct=False):
        self.check_id()
        self.check_id_range(id_val)

        mem_addr = self.allocator.memory_address(id_val)
        backing_alloc = self.allocator.backing_allocations[self.id]
        return backing_alloc.read_bytestring(mem_addr, size=size, force=force, direct=direct)

    def write_bytestring(self, id_val, string, force=False, direct=False):
        self.check_id()
        self.check_id_range(id_val)

        mem_addr = self.allocator.memory_address(id_val)
        backing_alloc = self.allocator.backing_allocations[self.id]
        return backing_alloc.write_bytestring(mem_addr, string, force=force, direct=direct)

    def flush(self, id_val=None, size=None):
        if not id_val is None:
            self.check_id()
            self.check_id_range(id_val)

            mem_addr = self.allocation.memory_address(id_val)
        else:
            mem_addr = id_val

        backing_alloc = self.allocator.backing_allocations[self.id]
        return backing_alloc.flush(mem_addr, size)

class VirtualAllocatorError(AllocatorError):
    pass

class VirtualAllocator(Allocator):
    ALLOCATION_CLASS = VirtualAllocation
    ZERO_MEMORY = True
    BASE_ADDRESS = None
    MAXIMUM_OFFSET = None
                                       
    def __init__(self, **kwargs):
        global allocators
        
        super(VirtualAllocator, self).__init__(**kwargs)
        
        self.zero_memory = kwargs.setdefault('zero_memory', self.ZERO_MEMORY)
        self.base_address = kwargs.setdefault('base_address', self.BASE_ADDRESS)
        self.maximum_offset = kwargs.setdefault('maximum_offset', self.MAXIMUM_OFFSET)
        
        virtual_allocators = filter(lambda x: not x == self and isinstance(x, VirtualAllocator), allocators)
        base_addrs = dict(map(lambda x: (x.base_address, None), virtual_allocators))

        if self.base_address is None:
            self.base_address = random.randrange(0x100000, 0x7FFFFF)
            self.base_address <<= 40

            while self.base_address in base_addrs:
                self.base_address = random.randrange(0x100000, 0x7FFFFF)
                self.base_address <<= 40

        if self.base_address in base_addrs:
            raise VirtualAllocatorError('base address already taken')

        self.backing_allocations = dict()

    def in_range(self, other_id, inclusive=False):
        allocator_addr = self.base_address
        allocator_end = allocator_addr+self.maximum_offset

        if inclusive:
            return allocator_addr <= other_id <= allocator_end
        else:
            return allocator_addr <= other_id < allocator_end

    def check_range(self, other_id, inclusive=False):
        if not self.in_range(other_id, inclusive):
            raise DiskError('address out of range')

    def offset_address(self, offset):
        return self.base_address + offset

    def memory_address(self, virtual_address):
        allocation = self.find(virtual_address)

        if allocation is None:
            return None

        backing_alloc = self.backing_allocations[allocation.id]
        delta = virtual_address - allocation.id

        return backing_alloc.id+delta

    def address(self, offset=0):
        if offset >= self.maximum_offset:
            raise VirtualAllocatorError('offset %d greater or eqaul to maximum offset %d' % (offset, self.maximum_offset))
        
        offset_addr = self.offset_address(offset)

        if offset_addr in self.allocations:
            return self.allocations[offset_addr].value.address()
        
        allocation = self.find(offset_addr)

        if not allocation is None:
            offset = offset_addr - allocation.id
            return allocation.address(offset)

        return VirtualAddress(offset=offset, allocator=self)

    def allocate(self, offset, size):
        global heap
        
        long = getattr(__builtin__, 'long', None)

        if long is None: # python3
            long = int

        if not isinstance(offset, (int, long)):
            raise AllocationError('offset must be an int or a long')

        offset = long(offset)

        if not isinstance(size, (int, long)):
            raise AllocationError('size must be an int or a long')

        if not self.maximum_offset is None and offset > self.maximum_offset:
            raise AllocationError('offset exceeds maximum offset')

        size = long(size)

        backing_allocation = heap.allocate(size)
        base_address = self.offset_address(offset)
        self.backing_allocations[base_address] = backing_allocation

        allocation = self.allocation_class(id=base_address
                                           ,size=size
                                           ,allocator=self)

        self.allocations[base_address] = allocation

        base_end = base_address+size
        consumed_allocations = filter(lambda x: not x == base_address and base_address <= x < base_end, self.allocations.keys())
        consumed_allocations.sort()

        for consumed_addr in consumed_allocations:
            self.consume_address(consumed_addr, base_address, base_end) 

        return allocation

    def reallocate(self, address, size):
        if not address in self.allocations:
            raise AllocatorError('address was not allocated by allocator')

        end_address = address+size
        backing_alloc = self.backing_allocations[address]
        backing_alloc.reallocate(size)

        allocation = self.allocations[address]
        allocation.size = size
        end_address = address+size

        consumed_allocations = filter(lambda x: not x == address and address <= x < end_address, self.allocations.keys())
        consumed_allocations.sort()

        for consumed_addr in consumed_allocations:
            self.consume_address(consumed_addr, address, end_address)

        return allocation
    
    def consume_address(self, consumed_address, start_address, end_address):
        if not consumed_address in self.allocations:
            raise AllocationError('consumed address not in allocations')

        if not start_address in self.allocations:
            raise AllocationError('start address not in allocations')

        if not consumed_address >= start_address or not consumed_address < end_address:
            raise AllocationError('consumed address not in the range of start and end')

        allocation = self.allocations[start_address].value
        backing = self.backing_allocations[start_address]
        size = end_address - start_address
        
        consumed_offset = consumed_address - start_address
        consumed_alloc = self.allocations[consumed_address].value
        consumed_backer = self.backing_allocations[consumed_address]
        consumed_size = consumed_alloc.size
        consumed_end = consumed_address + consumed_size
        consumed_offset_end = consumed_offset + consumed_size
        consumed_addresses = filter(lambda x: x+consumed_offset < size, consumed_alloc.addresses.keys())
            
        # shift and save the overlapped address objects
        for address_offset in consumed_addresses:
            address_obj = consumed_alloc.addresses[address_offset]
            address_obj.allocation = allocation
            address_obj.offset += consumed_offset
            allocation.addresses[consumed_offset+address_offset] = address_obj
            del consumed_alloc.addresses[address_offset]

        # do the same to the backing allocation
        consumed_addresses = filter(lambda x: x+consumed_offset < size, consumed_backer.addresses.keys())
            
        # shift and save the overlapped address objects
        for address_offset in consumed_addresses:
            address_obj = consumed_backer.addresses[address_offset]
            address_obj.allocation = backing
            address_obj.offset += consumed_offset
            backing.addresses[consumed_offset+address_offset] = address_obj
            del consumed_backer.addresses[address_offset]
                
        consumed_blocks = filter(lambda x: x+consumed_offset < size, consumed_backer.blocks.keys())
            
        # save the overlapped blocks into our allocation
        for block_offset in consumed_blocks:
            block = consumed_backer.blocks[block_offset]

            # this might look like it shouldn't work, but it does, because its underlying
            # address has been shifted to the new allocation!
            backing.set_block(int(block.address), block, True)
            
            del consumed_backer.blocks[block_offset]
        
        if consumed_end <= end_address:
            consumed_data = consumed_backer.read_bytestring(consumed_backer.id, force=True)
            backing.write_bytestring(backing.id+consumed_offset, consumed_data, force=True)
            consumed_alloc.free()
            return
        
        consumed_delta = size - consumed_offset
        consumed_data = consumed_backer.read_bytestring(consumed_backer.id, size=consumed_delta, force=True)
        backing.write_bytestring(allocation.id+consumed_offset, consumed_data, force=True)
            
        # this region only overlaps partially, move the beginning of the consumed region
        # to the end of the new allocation
        unconsumed_addresses = filter(lambda x: x+consumed_offset >= size, consumed_alloc.addresses.keys())

        for unconsumed_offset in unconsumed_addresses:
            new_offset = unconsumed_offset - consumed_delta
            unconsumed_address = consumed_alloc.addresses[unconsumed_offset]
            consumed_alloc.addresses[new_offset] = unconsumed_address
            del consumed_alloc.address[unconsumed_offset]

            unconsumed_address.allocation = consumed_alloc
            unconsumed_address.offset -= consumed_delta

        # do it again for the backing allocation
        unconsumed_addresses = filter(lambda x: x+consumed_offset >= size, consumed_backer.addresses.keys())

        for unconsumed_offset in unconsumed_addresses:
            new_offset = unconsumed_offset - consumed_delta
            unconsumed_address = consumed_backer.addresses[unconsumed_offset]
            consumed_backer.addresses[new_offset] = unconsumed_address
            del consumed_backer.address[unconsumed_offset]

            unconsumed_address.allocation = consumed_backer
            unconsumed_address.offset -= consumed_delta
            
        unconsumed_blocks = filter(lambda x: x+consumed_offset >= size, consumed_backer.blocks.keys())

        for unconsumed_offset in unconsumed_blocks:
            new_offset = unconsumed_offset - consumed_delta
            unconsumed_block = consumed_backer.blocks[unconsumed_offset]
            consumed_alloc.blocks[new_offset] = unconsumed_block
            del consumed_backer.blocks[unconsumed_offset]
                    
            unconsumed_block.address.allocation = consumed_alloc
            unconsumed_block.address.offset -= consumed_delta

        unconsumed_address = consumed_backer.id + consumed_delta
        unconsumed_size = consumed_backer.size - consumed_delta
        memmove(consumed_backer.id, unconsumed_address, unconsumed_size)
        consumed_backer.reallocate(unconsumed_size)

        del self.allocations[consumed_address]
        self.allocations[end_address] = consumed_alloc

        del self.backing_allocations[consumed_address]
        self.backing_allocations[end_address] = consumed_backer

    def free(self, address):
        if address not in self.allocations:
            raise AllocatorError('no such address allocated: 0x%x' % address)

        allocation = self.allocations[address].value
        backing_alloc = self.backing_allocations[address]
        backing_alloc.invalidate()
        backing_alloc.free()
        del self.backing_allocations[address]

        allocation.invalidate()
        allocation.address = 0
        allocation.size = 0
        del self.allocations[address]
