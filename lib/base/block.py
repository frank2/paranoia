#!/usr/bin/env python

from paranoia.base.paranoia_agent import ParanoiaAgent, ParanoiaError
from paranoia.base.size import Size
from paranoia.fundamentals import align, bytelist_to_bitlist, hexdump, bitdump

__all__ = ['BlockError', 'Block', 'BlockLink', 'BlockChain']
    
class BlockError(ParanoiaError):
    pass

class Block(ParanoiaAgent):
    ADDRESS = None
    VALUE = None
    STATIC = False
    BUFFER = True
    
    def __init__(self, **kwargs):
        from paranoia.base.address import Address

        self.init_finished = False

        self.address = kwargs.setdefault('address', self.ADDRESS)

        if self.address is None:
            raise BlockError('address cannot be None')

        if not isinstance(self.address, Address):
            raise BlockError('address must be an Address instance')

        self.buffer = kwargs.setdefault('buffer', self.BUFFER)
        self.value = kwargs.setdefault('value', self.VALUE)
        self.static = kwargs.setdefault('static', self.STATIC)

        if not self.value is None:
            self.set_value(value)

        self.init_finished = True

    def is_static(self):
        return self.static and self.init_finished

    def get_value(self, force=False):
        if self.value is None or force or not self.buffer:
            self.value = self.address.read_byte()
            
        return self.value

    def set_value(self, value, force=False):
        if self.is_static():
            raise BlockError('cannot write to static block')
        
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
        mask = 1 << (7 - bit_offset)

        if bit_value == 1:
            value |= mask
        else:
            value &= ~mask

        self.set_value(value, force)

    def flush(self):
        if self.value is None:
            return

        if self.is_static():
            raise BlockError('cannot write to static region')
        
        self.address.write_byte(self.value)

        if self.buffer:
            self.value = None

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
            return self.address.get_block().get_value(force)

        lb = self.address.get_block(0)
        rb = self.address.get_block(1)
        value = 0

        for i in xrange(8):
            offset = self.shift + i

            if offset >= 8:
                cb = rb
            else:
                cb = lb

            value <<= 1
            value |= cb.get_bit(offset % 8, force)

        return value

    def set_value(self, value, force=False):
        if self.is_static():
            raise BlockError('cannot write to static link')
        
        if not 0 <= value < 256:
            raise BlockError('value must be 0 <= value < 256')

        if self.shift == 0:
            self.address.get_block().set_value(value, force)
        else:
            lb = self.address.get_block(0)
            rb = self.address.get_block(1)

            for i in reversed(xrange(8)):
                offset = self.shift + i

                if offset >= 8:
                    cb = rb
                else:
                    cb = lb

                cb[offset % 8] = value & 1
                value >>= 1

        if force or not self.buffer:
            self.flush()

    def flush(self):
        if self.is_static():
            raise BlockError('cannot write to static link')
        
        if self.shift == 0:
            self.address.get_block().flush()
        else:
            lb = self.address.get_block(0)
            rb = self.address.get_block(1)
            
            lb.flush()
            rb.flush()

class BlockChain(ParanoiaAgent):
    ADDRESS = None
    ALLOCATOR = None # default allocator gets set to heap in allocator.py
    AUTO_ALLOCATE = True
    SHIFT = 0
    BUFFER = True
    SIZE = Size(bits=0)
    BIND = False
    STATIC = False
    MAXIMUM_SIZE = None
    PARSE_MEMORY = False

    def __init__(self, **kwargs):
        from paranoia.base.address import Address
        from paranoia.base.allocator import Allocator

        self.init_finished = False
        
        self.address = kwargs.setdefault('address', self.ADDRESS)

        if not self.address is None and not isinstance(self.address, Address):
            raise BlockError('address must be an Address object')

        self.allocator = kwargs.setdefault('allocator', self.ALLOCATOR)

        if not isinstance(self.allocator, Allocator):
            raise BlockError('allocator must be an Allocator instance')

        self.auto_allocate = kwargs.setdefault('auto_allocate', self.AUTO_ALLOCATE)
        self.shift = kwargs.setdefault('shift', self.SHIFT)
        self.buffer = kwargs.setdefault('buffer', self.BUFFER)
        self.bind = kwargs.setdefault('bind', self.BIND)
        self.static = kwargs.setdefault('static', self.STATIC)
        self.allocation = None

        maximum_size = kwargs.setdefault('maximum_size', self.MAXIMUM_SIZE)
        self.set_maximum_size(maximum_size)
            
        chain_length = kwargs.setdefault('size', self.SIZE)
        self.set_size(chain_length)

        if self.address is None and not self.auto_allocate:
            raise BlockError('address is None and auto_allocate is False')

        if self.address is None:
            self.allocation = self.allocator.allocate(self.blockspan())
            self.address = self.allocation.address()

        self.init_finished = True

    def get_link(self, index):
        if index < 0:
            index += len(self)

        if index < 0 or index >= len(self):
            raise IndexError(index)

        return BlockLink(address=self.address.fork(index)
                         ,shift=self.shift
                         ,buffer=self.buffer
                         ,static=self.static)

    def is_bound(self):
        return self.bind and self.init_finished

    def is_static(self):
        return self.static and self.init_finished

    def is_allocated(self):
        return not self.allocation is None

    def set_maximum_size(self, max_size):
        if self.is_bound():
            raise BlockError('cannot resize bound chain')
        
        if max_size is None:
            self.maximum_size = None
        elif isinstance(max_size, Size):
            self.maximum_size = Size(bits=max_size.bits)
        else:
            raise BlockError('size must be a Size object')

        if not self.maximum_size is None and self.size.bits > self.maximum_size.bits:
            raise BlockError('new maximum exceeds current size')

    def set_size(self, chain_length):
        if self.is_bound():
            raise BlockError('cannot resize bound chain')
        
        self.flush()
        
        if isinstance(chain_length, Size):
            self.size = Size(bits=chain_length.bits)
        else:
            raise BlockError('size must be a Size object')

        if not self.maximum_size is None and self.size.bits > self.maximum_size.bits:
            raise BlockError('new size exceeds maximum size')

        if not self.allocation is None:
            self.allocation.reallocate(self.blockspan())

    def set_shift(self, shift):
        if not self.is_static():
            self.flush()

        if not 0 <= shift < 8:
            raise BlockError('shift must be 0 <= shift < 8')
        
        old_span = self.blockspan()
        
        self.shift = shift

        new_span = self.blockspan()

        if not old_span == new_span and not self.allocation is None and not self.is_bound():
            self.allocation.reallocate(self.blockspan())

    def blockspan(self):
        return int(align(self.size.bits + self.shift, 8)/8)

    def bit_iterator(self):
        for i in xrange(self.size.bits):
            yield self.get_link(int(i/8)).get_bit(i%8)

    def link_iterator(self):
        for i in xrange(self.size.byte_length()):
            yield self.get_link(i)

    def byte_iterator(self):
        for link in self.link_iterator():
            yield int(link)

    def block_iterator(self):
        # iterate over the blocks this blockchain uses
        for i in xrange(self.blockspan()):
            yield self.address.get_block(i)

    def flush(self):
        if not self.address is None:
            self.address.flush(size=self.blockspan())

    def read_bits(self, bit_offset=0, size=None, force=False):
        if not size is None and not isinstance(size, (int, Size)):
            raise BlockError('size must be an int or a Size object')

        if not size is None:
            stop = bit_offset + int(size)
        else:
            stop = int(self.size)

        if stop > int(self.size):
            raise BlockError('size exceeds chain length')

        bits = list()
        
        for i in range(bit_offset, stop):
            bits.append(self.get_link(int(i/8)).get_bit(i%8, force))

        return bits

    def read_bytes(self, offset=0, size=None, force=False):
        if not size is None and not isinstance(size, (int, Size)):
            raise BlockError('size must be an int or a Size object')

        if not size is None:
            if isinstance(size, int):
                stop = offset + int(size)
            else:
                stop = offset + size.byte_length()
        else:
            stop = self.size.byte_length()

        if stop > self.size.byte_length():
            raise BlockError('size exceeds chain length')

        byte_vals = list()

        for i in range(offset, stop):
            byte_vals.append(self.get_link(i).get_value(force))

        return byte_vals

    def read_bytestring(self, offset=0, size=None, force=False):
        return bytearray(self.read_bytes(offset, size, force))

    def read_string(self, offset=0, size=None, encoding='ascii', force=False):
        return self.read_bytestring(offset, size, force).decode(encoding)

    def read_blocks(self, offset=0, size=None, force=False):
        if not size is None and not isinstance(size, (int, Size)):
            raise BlockError('size must be an int or a Size object')

        if not size is None:
            if isinstance(size, int):
                stop = offset + int(size)
            else:
                stop = offset + size.byte_length()
        else:
            stop = self.blockspan()

        if stop > self.blockspan():
            raise BlockError('size exceeds blockspan')

        block_vals = list()

        for i in range(offset, stop):
            block_vals.append(self.address.get_block(i).get_value(force))

        return block_vals

    def write_bits(self, bit_list, bit_offset=0, force=False):
        bits = len(bit_list)

        if bit_offset+bits > int(self.size):
            raise BlockError('bitlist exceeds region size')

        for i in range(bit_offset, bits+bit_offset):
            self.get_link(int(i/8)).set_bit(i%8, bits[i-bit_offset], force)

        if not self.buffer and not force:
            self.flush()

    def write_bytes(self, byte_list, offset=0, force=False):
        bytecount = len(byte_list)

        if offset+bytecount > self.size.byte_length():
            raise BlockError('bytelist exceeds region size')

        for i in range(offset, offset+bytecount):
            self.get_link(i).set_value(byte_list[i], force)

        if not self.buffer and not force:
            self.flush()

    def write_bytestring(self, byte_array, offset=0, force=False):
        self.write_bytes(list(byte_array), offset, force)

    def write_string(self, str_val, encoding='ascii', offset=0, force=False):
        self.write_bytestring(bytearray(str_val, encoding), offset, force)

    def write_blocks(self, block_list, offset=0, force=False):
        block_count = len(block_list)

        if offset+block_count > self.blockspan():
            raise BlockError('blocklist exceeds region blockspan')

        for i in range(offset, offset+block_count):
            self.address.get_block(i).set_value(block_list[i], force)

        if not self.buffer and not force:
            self.flush()

    def hexdump(self, label=None):
        hexdump(int(self.address), self.blockspan(), label)

    def bitdump(self, label=None):
        bitdump(int(self.address), int(self.size), self.shift, label)

    def __getitem__(self, index):
        return self.get_link(index)

    def __setitem__(self, index, block_or_int):
        if not isinstance(block, (Block, BlockLink, int)):
            raise BlockError('block must be a BlockLink, Block or int')

        self[index].set_value(int(block_or_int))

    def __iter__(self):
        return self.link_iterator()

    def __len__(self):
        return self.size.byte_length()

    def __del__(self):
        if not self.allocation is None:
            self.allocation.free()
