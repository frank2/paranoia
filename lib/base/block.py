#!/usr/bin/env python

from paranoia.base.paranoia_agent import ParanoiaAgent, ParanoiaError
from paranoia.converters import align

class BitspanError(ParanoiaError):
    pass

class Bitspan(ParanoiaAgent):
    BYTES = None
    BITS = 0
    
    def __init__(self, **kwargs):
        byte_count = kwargs.setdefault('bytes', self.BYTES)
        bit_count = kwargs.setdefault('bits', self.BITS)

        if not bit_count is None and not isinstance(bit_count, int):
            raise BitspanError('bit count must be an int')

        if not byte_count is None and not isinstance(byte_count, int):
            raise BitspanError('byte count must be an int')
        
        if byte_count is None and not bit_count is None:
            self.set_bits(bit_count)
        elif bit_count is None and not byte_count is None:
            self.set_bytes(byte_count)
        elif not bit_count is None and not byte_count is None:
            if bit_count > byte_count * 8:
                self.set_bits(bit_count)
            else:
                self.set_bytes(byte_count)
        else:
            raise BitspanError('must provide either bits or bytes to constructor')

    def set_bits(self, bits):
        self.bits = bits

    def set_bytes(self, byte_count):
        self.bits = byte_count * 8

    def byte_offset(self):
        return int(self.bits/8)

    def byte_length(self):
        return int(align(self.bits, 8)/8)

    def __int__(self):
        return self.bits
    
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
    BUFFER = True
    SIZE = 0

    def __init__(self, **kwargs):
        from paranoia.base.address import Address
        
        self.address = kwargs.setdefault('address', self.ADDRESS)

        if self.address is None:
            raise BlockError('address cannot be None')

        if not isinstance(self.address, Address):
            raise BlockError('address must be an Address object')

        self.shift = kwargs.setdefault('shift', self.SHIFT)
        self.buffer = kwargs.setdefault('buffer', self.BUFFER)
        self.chain = list()

        chain_length = kwargs.setdefault('size', self.SIZE)
        self.set_length(chain_length)

    def set_size(self, chain_length):
        if isinstance(chain_length, int): # interpret as bytespan
            self.size = Bitspan(bytes=chain_length)
        elif isinstance(chain_length, Bitspan):
            self.size = chain_length
        else:
            raise BlockError('size must be an integer representing the bytespan or a Bitspan object')
        
        self.chain = [BlockLink(address=self.address.fork(x)
                                ,shift=self.shift
                                ,buffer=self.buffer) for x in xrange(self.size.byte_length())]

    def set_shift(self, shift):
        for link in self.chain:
            link.flush()
            link.shift = shift

        self.shift = shift

    def bit_iterator(self):
        for i in xrange(self.size.bits):
            yield self[i/8][i%8]

    def byte_iterator(self):
        for link in self.chain:
            yield int(link)

    def link_iterator(self):
        for link in self.chain:
            yield link

    def block_iterator(self):
        block_count = align(self.shift + self.size.bits, 8)/8

        for i in block_count:
            yield self.address.get_block(i)

    def flush(self):
        for block in self.link_iterator():
            block.flush()

    def __getitem__(self, index):
        if index < 0:
            index += len(self.chain)

        if index < 0 or index >= len(self.chain):
            raise IndexError(index)

        return self.chain[index]

    def __setitem__(self, index, block_or_int):
        if not isinstance(block, (Block, BlockLink, int)):
            raise BlockError('block must be a BlockLink, Block or int')

        self.chain[index].set_value(int(block_or_int))

