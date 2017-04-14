#!/usr/bin/env python

from paranoia.base.paranoia_agent import ParanoiaAgent, ParanoiaError
from paranoia.base.allocator import IntPtr
from paranoia.base.address import Address

__all__ = ['BlockError', 'Block']

class BlockError(ParanoiaError):
    pass

class Block(ParanoiaAgent):
    ADDRESS = None
    VALUE = None
    BUFFER = False
    SHIFT = 0
    
    def __init__(self, **kwargs):
        self.address = kwargs.setdefault('address', self.ADDRESS)

        if self.address is None:
            raise BlockError('address cannot be None')

        if not isinstance(self.address, Address):
            raise BlockError('address must be an Address instance')

        self.buffer = kwargs.setdefault('buffer', self.BUFFER)
        self.value = kwargs.setdefault('value', self.VALUE)
        self.shift = kwargs.setdefault('shift', self.SHIFT)

        self.set_shift(self.shift)

        if not self.value is None:
            self.set_value(value)

    def superblocks(self, **kwargs):
        if self.shift == 0:
            return (self, None)
        else:
            b1_kwargs = dict(kwargs.items()[:])
            b2_kwargs = dict(kwargs.items()[:])
            
            b1_kwargs['address'] = self.address.fork(0)
            b1 = self.__class__(**b1_kwargs)

            b2_kwargs['address'] = self.address.fork(1)
            b2 = self.__class__(**b2_kwargs)
            
            return (b1, b2)

    def set_shift(self, shift):
        if not 0 <= shift < 8:
            raise BlockError('shift must be 0 <= shift < 8')

        self.shift = shift

    def get_value(self, force=False):
        if self.value is None or force or not self.buffer:
            self.value = self.interblock_read()
            
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
            value |= bit_value << (7 - bit_offset)
        else:
            value &= (bit_value << (7 - bit_offset)) ^ 0xFF

        self.set_value(value, force)

    def interblock_read(self):
        if self.shift == 0:
            return self.address.read_bytes(1)[0]
        else:
            lb, rb = self.superblocks()
            bits = list()

            for i in xrange(8):
                offset = i + self.shift

                if offset >= 8:
                    cb = rb
                else:
                    cb = lb

                bits.append(cb[offset % 8])

            bits.reverse()
            value = 0

            for b in bits:
                value <<= 1
                value |= b

            return value

    def interblock_write(self, value):
        if not 0 <= value < 256:
            raise BlockError('value must be 0 <= value < 256')
        
        if self.shift == 0:
            self.address.write_bytes([value])
        else:
            data = list()

            for i in xrange(8):
                data.append(value & 1)
                value >>= 1

            data.reverse()
            
            lb, rb = self.superblocks(buffer=True)

            for i in xrange(8):
                offset = i + self.shift

                if offset >= 8:
                    cb = rb
                else:
                    cb = lb

                cb[offset % 8] = data[i]

            lb.flush()
            rb.flush()

        self.value = None

    def flush(self):
        self.interblock_write(self.value)

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
