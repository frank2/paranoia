#!/usr/bin/env python

import platform
import ctypes
import sys
import traceback

try:
    import __builtin__
except ImportError: # python3
    import builtins as __builtin__

from paranoia.base.paranoia_agent import ParanoiaAgent, ParanoiaError
from paranoia.converters import align, string_address

allocators = set()
memory = None
heap = None

__all__ = ['AllocatorError', 'AllocationError', 'Allocator', 'Allocation']

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

class AllocatorError(ParanoiaError):
    pass

class AllocationError(ParanoiaError):
    pass

class AddressError(ParanoiaError):
    pass

class Address(ParanoiaAgent):
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

    def value(self):
        if self.allocation is None:
            raise AddressError('address is invalid')
        
        return self.allocation.id + self.offset

    def set_offset(self, value):
        if self.allocation is None:
            # if there's no allocation, we assume this address is just an abstract memory pointer. find its
            # allocation in memory and, if it doesn't exist, create it
            global memory

            self.allocation = Allocator.find_all(self.offset)

            if not self.allocation is None:
                self.offset = self.offset - self.allocation.id
            else:
                self.allocation = memory.allocate(self.offset)
                self.offset = 0
        else:
            self.offset = value

    def fork(self, offset):
        return Address(offset=self.offset+offset, allocation=self.allocation)

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
        self.allocation.flush(int(self)+offset, size)

    def __int__(self):
        return self.value()

    def __repr__(self):
        return '<Address:0x%X>' % (int(self))

    def __hash__(self):
        return hash(int(self))

class BlockError(ParanoiaError):
    pass

class Block(ParanoiaAgent):
    ADDRESS = None
    VALUE = None
    BUFFER = True
    
    def __init__(self, **kwargs):
        self.address = kwargs.setdefault('address', self.ADDRESS)

        if self.address is None:
            raise BlockError('address cannot be None')

        if not isinstance(self.address, Address):
            raise BlockError('address must be an Address instance')

        self.buffer = kwargs.setdefault('buffer', self.BUFFER)
        self.value = kwargs.setdefault('value', self.VALUE)

        if not self.value is None:
            self.set_value(value)

    def get_value(self, force=False):
        if self.value is None or force or not self.buffer:
            self.value = self.address.read_byte()
            
        return self.value

    def set_value(self, value, force=False):
        if not 0 <= value < 256:
            raise BlockError('value must be 0 <= value < 256')
        
        self.value = value

        if force or not self.buffer:
            self.flush()

    def get_bit(self, bit_offset, force=False):
        if not 0 <= bit_offset < 8:
            raise BlockError('bit offset must be 0 <= offset < 8')

        return (self.get_value(force) >> (7 - bit_offset)) & 1

    def set_bit(self, bit_offset, bit_value, force=False):
        if not 0 <= bit_offset < 8:
            raise BlockError('bit offset must be 0 <= offset < 8')

        if not 0 <= bit_value <= 1:
            raise BlockError('bit must be between 0 and 1')

        value = self.get_value(force)

        if bit_value == 1:
            value |= 1 << (7 - bit_offset)
        else:
            value &= ~(1 << (7 - bit_offset))

        self.set_value(value, force)

    def flush(self):
        if self.value is None:
            return
        
        self.address.write_byte(self.value)

    def __getitem__(self, index):
        if index < 0:
            index += 8
            
        if not 0 <= index < 8:
            raise IndexError(index)

        return self.get_bit(index)

    def __setitem__(self, index, value):
        if index < 0:
            index += 8
            
        if not 0 <= index < 8:
            raise IndexError(index)

        if not 0 <= value <= 1:
            raise ValueError(value)

        self.set_bit(index, value)

    def __iter__(self):
        for i in xrange(8):
            yield self[i]

    def __int__(self):
        return self.get_value()

    def __repr__(self):
        return '<Block:0x%X/%d>' % (int(self.address), self.get_value())

class BlockLink(Block):
    SHIFT = 0

    def __init__(self, **kwargs):
        super(BlockLink, self).__init__(**kwargs)
        
        self.shift = kwargs.setdefault('shift', self.SHIFT)

    def get_value(self, force=False):
        if self.shift == 0:
            self.value = self.address.get_block().get_value(force)
            return self.value

        if self.value is None or force or not self.buffer:
            bitlist = list()
            lb = self.address.get_block(0)
            rb = self.address.get_block(1)
            self.value = 0

            for i in xrange(8):
                offset = self.shift + i

                if offset >= 8:
                    cb = rb
                else:
                    cb = lb

                self.value <<= 1
                self.value |= cb.get_bit(offset % 8, force)

        return self.value

    def set_value(self, value, force=False):
        if not 0 <= value < 256:
            raise BlockError('value must be 0 <= value < 256')
        
        self.value = value

        if self.shift == 0:
            self.address.get_block().set_value(value, force)
        elif force or not self.buffer:
            self.flush()

    def flush(self):
        if self.value is None:
            return

        if self.shift == 0:
            self.address.get_block().flush()
            return

        lb = self.address.get_block(0)
        rb = self.address.get_block(1)
        value = self.value

        for i in reversed(xrange(8)):
            offset = self.shift + i

            if offset >= 8:
                cb = rb
            else:
                cb = lb

            cb[offset % 8] = value & 1
            value >>= 1

        lb.flush()
        rb.flush()

        self.value = None

class BlockChain(ParanoiaAgent):
    ADDRESS = None
    SHIFT = 0
    CHAIN_LENGTH = 0

    def __init__(self, **kwargs):
        self.address = kwargs.setdefault('address', self.ADDRESS)

        if self.address is None:
            raise BlockError('address cannot be None')

        if not isinstance(self.address, Address):
            raise BlockError('address must be an Address object')

        self.shift = kwargs.setdefault('shift', self.SHIFT)

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

        self.blocks = dict()

    def set_buffering(self, buffering):
        if not isinstance(buffering, bool):
            raise AllocationError('buffering should be a boolean')

        self.buffer = buffering

        for block_id in self.blocks:
            self.blocks[block_id].buffer = self.buffer

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

    def address(self, offset=0):
        return Address(offset=offset, allocation=self)

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
            size = self.size * 8
            
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

        print hex(back_addr), padding_back, back_block.get_value()

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

        for i in range(start_delta, end_delta):
            if i in self.blocks and not self.blocks[i].value is None and len(block_range) == 0:
                block_range.append(i)
            elif (not i in self.blocks or self.blocks[i].value is None) and len(block_range) == 1:
                block_range.append(i)

                block_start, block_end = block_range
                byte_array = bytes(map(lambda x: self.blocks[x].value, range(*block_range)))
                string_buffer = ctypes.create_string_buffer(byte_array)
                string_address = ctypes.addressof(string_buffer)

                memmove(self.id+block_start, string_address, len(byte_array))

                for i in range(*block_range):
                    self.blocks[i].value = None

                block_range = list()

    def invalidate(self):
        for block_index in self.blocks:
            block = self.blocks[block_index]
            block.address.allocation = None

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
        self.free()

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
    
class Allocator(ParanoiaAgent):
    BUFFER = True
    
    def __init__(self, **kwargs):
        global allocators

        self.buffer = kwargs.setdefault('buffer', self.BUFFER)
        self.allocations = dict()

        allocators.add(self)

    def set_buffering(self, buffering):
        if not isinstance(buffering, bool):
            raise AllocatorError('buffering must be a bool')

        self.buffer = buffering

        for allocation_id in self.allocations:
            self.allocations[allocation_id].set_buffering(self.buffer)

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

        return self.allocations[keys[0]]

    def __del__(self):
        global allocators

        if not allocators is None:
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
            raise AllocatorError('address already has allocation')

        self.allocations[address] = MemoryAllocation(id=address, size=1, allocator=self, buffer=self.buffer)

        return self.allocations[address]

    def reallocate(self, address, size):
        if not address in self.allocations:
            raise AllocatorError('address was not allocated by allocator')

        end_address = address+size

        allocation = self.allocations[address]
        allocation.size = size

        consumed_allocations = filter(lambda x: not x == address and address <= x < end_address, self.allocations.keys())
        consumed_allocations.sort()

        for consumed_addr in consumed_allocations:
            consumed_offset = consumed_addr - address
            consumed_alloc = self.allocations[consumed_addr]
            consumed_size = consumed_alloc.size
            consumed_end = consumed_addr + consumed_size
            consumed_offset_end = consumed_offset + consumed_size
            consumed_blocks = filter(lambda x: x+consumed_offset < size, consumed_alloc.blocks.keys())

            # save the overlapped blocks into our allocation

            for consumed_offset in consumed_blocks:
                block = consumed_alloc.blocks[consumed_offset]
                allocation.set_block(int(block.address), block, True)

            if consumed_end > end_address:
                # move the beginning of this region to the end of our reallocated region
                unconsumed_blocks = filter(lambda x: x+consumed_offset >= size, consumed_alloc.blocks.keys())
                unconsumed_delta = size - consumed_offset

                for unconsumed_offset in unconsumed_blocks:
                    consumed_alloc.blocks[unconsumed_offset].offset -= unconsumed_delta

                consumed_alloc.id = end_address
                del self.allocations[consumed_addr]
                self.allocations[end_address] = consumed_alloc
            else:
                del self.allocations[consumed_addr]

        return allocation

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
        
        allocation = Allocation(id=heap_address
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

        if address not in self.address_map:
            raise AllocatorError('no such address allocated: 0x%x' % address)

        allocation = self.allocations[address]
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
        if address not in self.address_map:
            raise AllocatorError('no such address allocated: 0x%x' % address)

        allocation = self.address_map[address]

        memset(address, 0, allocation.size)
        free(address)
        allocation.address = 0
        allocation.size = 0
        
        del self.address_map[address]

    def __del__(self):
        for address in self.address_map:
            self.free(address)

heap = HeapAllocator()
