#!/usr/bin/env python

from paranoia.base.paranoia_agent import ParanoiaAgent, ParanoiaError
from paranoia.fundamentals import align

__all__ = ['SizeError', 'Size']

class SizeError(ParanoiaError):
    pass

class Size(ParanoiaAgent):
    BITS = None
    BYTES = None
    
    def __init__(self, **kwargs):
        bits = kwargs.setdefault('bits', self.BITS)
        byte_count = kwargs.setdefault('bytes', self.BYTES)

        if bits is None and byte_count is None:
            raise SizeError('size must be given either a bitcount or a bytecount')

        if not byte_count is None:
            self.set_bytes(byte_count)
        else:
            self.set_bits(bits)

    def set_bytes(self, byte_count):
        if not isinstance(byte_count, int):
            raise SizeError('size must be an int')

        self.set_bits(byte_count * 8)

    def set_bits(self, bit_count):
        if not isinstance(bit_count, int):
            raise SizeError('size must be an int')

        if bit_count < 0:
            raise SizeError('size cannot be negative')

        self.bits = bit_count

    def byte_offset(self):
        return int(self.bits/8)
    
    def byte_length(self):
        return int(align(self.bits, 8)/8)

    def __int__(self):
        return self.bits

    def __add__(self, other):
        if not isinstance(other, (int, Size)):
            raise SizeError('addend must be an int or a Size object')

        return self.__class__(bits=self.bits + int(other))

    def __radd__(self, other):
        return self + other

    def __iadd__(self, other):
        self.set_bits(int(self + other))

    def __sub__(self, other):
        if not isinstance(other, (int, Size)):
            raise SizeError('subtractor must be an int or a Size object')

        return self.__class__(bits=self.bits - int(other))

    def __rsub__(self, other):
        if not isinstance(other, (int, Size)):
            raise SizeError('subtractor must be an int or a Size object')
        
        return self.__class__(bits=int(other) - self.bits)

    def __isub__(self, other):
        self.set_bits(int(self - other))

    def __mul__(self, other):
        if not isinstance(other, (int, Size)):
            raise SizeError('multiplicant must be an int or a Size object')

        return self.__class__(bits=self.bits * int(other))

    def __rmul__(self, other):
        return self * other

    def __imul__(self, other):
        self.set_bits(int(self * other))

    def __div__(self, other):
        if not isinstance(other, (int, Size)):
            raise SizeError('divisor must be an int or a Size object')

        if int(other) == 0:
            raise SizeError('divisor cannot be 0')
        
        return self.__class__(bits=int(self.bits / int(other)))

    def __rdiv__(self, other):
        if not isinstance(other, (int, Size)):
            raise SizeError('subtractor must be an int or a Size object')

        if self.bits == 0:
            raise SizeError('divisor cannot be 0')
        
        return self.__class__(bits=int(int(other) / self.bits))

    def __idiv__(self, other):
        self.set_bits(int(self / other))

    def __mod__(self, other):
        if not isinstance(other, (int, Size)):
            raise SizeError('divisor must be an int or a Size object')

        if int(other) == 0:
            raise SizeError('divisor cannot be 0')
        
        return self.__class__(bits=int(self.bits % int(other)))

    def __rmod__(self, other):
        if not isinstance(other, (int, Size)):
            raise SizeError('subtractor must be an int or a Size object')

        if self.bits == 0:
            raise SizeError('divisor cannot be 0')
        
        return self.__class__(bits=int(int(other) % self.bits))

    def __imod__(self, other):
        self.set_bits(int(self % other))

    def __cmp__(self, other):
        return cmp(self.bits, int(other))
