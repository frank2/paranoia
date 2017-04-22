#!/usr/bin/env python

from paranoia.base.paranoia_agent import ParanoiaAgent, ParanoiaError
from paranoia.base.size import Size
from paranoia.fundamentals import align

__all__ = ['BlockError', 'Block', 'BlockLink', 'BlockChain']
    
class BlockError(ParanoiaError):
    pass

class Block(ParanoiaAgent):
    ADDRESS = None
    VALUE = None
    BUFFER = True
    
    def __init__(self, **kwargs):
        from paranoia.base.address import Address

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
        mask = 1 << (7 - bit_offset)

        if bit_value == 1:
            value |= mask
        else:
            value &= ~mask

        self.set_value(value, force)

    def flush(self):
        if self.value is None:
            return
        
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
    SIZE = 0
    MAXIMUM_SIZE = None
    PARSE_MEMORY = False

    def __init__(self, **kwargs):
        from paranoia.base.address import Address
        from paranoia.base.allocator import Allocator
        
        self.address = kwargs.setdefault('address', self.ADDRESS)

        if not self.address is None and not isinstance(self.address, Address):
            raise BlockError('address must be an Address object')

        self.allocator = kwargs.setdefault('allocator', self.ALLOCATOR)

        if not isinstance(self.allocator, Allocator):
            raise BlockError('allocator must be an Allocator instance')

        self.auto_allocate = kwargs.setdefault('auto_allocate', self.AUTO_ALLOCATE)
        self.shift = kwargs.setdefault('shift', self.SHIFT)
        self.buffer = kwargs.setdefault('buffer', self.BUFFER)
        self.chain = list()
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

        parse_memory = kwargs.setdefault('parse_memory', self.PARSE_MEMORY)

        if 'bit_data' in kwargs:
            self.parse_bit_data(kwargs['bit_data'])
            self.flush()
        elif 'link_data' in kwargs:
            self.parse_link_data(kwargs['link_data'])
            self.flush()
        elif 'block_data' in kwargs:
            self.parse_block_data(kwargs['block_data'])
            self.flush()
        elif parse_memory:
            self.parse_memory()
            self.flush()

    def set_maximum_size(self, max_size):
        if max_size is None:
            self.maximum_size = None
        elif isinstance(max_size, int): # interpret as bytespan
            self.maximum_size = Size(bytes=max_size)
        elif isinstance(max_size, Size):
            self.maximum_size = Size(bits=max_size.bits)
        else:
            raise BlockError('size must be an integer representing the bytespan or a Size object')

        if not self.maximum_size is None and self.size.bits > self.maximum_size.bits:
            raise BlockError('new maximum exceeds current size')

    def set_size(self, chain_length):
        self.flush()
        
        if isinstance(chain_length, int): # interpret as bytespan
            self.size = Size(bytes=chain_length)
        elif isinstance(chain_length, Size):
            self.size = Size(bits=chain_length.bits)
        else:
            raise BlockError('size must be an integer representing the bytespan or a Size object')

        if not self.maximum_size is None and self.size.bits > self.maximum_size.bits:
            raise BlockError('new size exceeds maximum size')

        if not self.allocation is None:
            self.allocation.reallocate(self.blockspan())

    def set_shift(self, shift):
        self.flush()
        
        old_span = self.blockspan()
        
        self.shift = shift

        new_span = self.blockspan()

        if not old_span == new_span and not self.allocation is None:
            self.allocation.reallocate(self.blockspan())

    def parse_bit_data(self, bit_data):
        for i in xrange(len(bit_data)):
            if i >= self.size.bits:
                break

            self[int(i/8)][i%8] = bit_data[i]

    def parse_link_data(self, link_data):
        if isinstance(link_data, str):
            link_data = map(ord, link_data)

        for i in xrange(len(link_data)):
            if i >= len(self):
                break
            
            self[i].set_value(link_data[i])

    def parse_block_data(self, block_data):
        if isinstance(block_data, str):
            block_data = map(ord, block_data)

        blocks = list(self.block_iterator())
        
        for i in xrange(len(block_data)):
            if i >= len(blocks):
                break
            
            blocks[i].set_value(block_data[i])

    def parse_memory(self):
        block_bytes = list()

        for block in self.block_iterator():
            block_bytes.append(block.get_value(force=True))

        self.parse_block_data(block_bytes)

    def blockspan(self):
        return int(align(self.size.bits + self.shift, 8)/8)

    def bit_iterator(self):
        for i in xrange(self.size.bits):
            yield self[int(i/8)][i%8]

    def link_iterator(self):
        for i in xrange(self.size.byte_length()):
            yield self[i]

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

    def __getitem__(self, index):
        if index < 0:
            index += len(self)

        if index < 0 or index >= len(self):
            raise IndexError(index)

        return BlockLink(address=self.address.fork(index)
                         ,shift=self.shift
                         ,buffer=self.buffer)

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
