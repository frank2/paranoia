#!/usr/bin/env python

from paranoia.base import address, memory_region, numeric_region

__all__ = ['PointerError', 'Pointer', 'Pointer32', 'Pointer64']

class PointerError(numeric_region.NumericRegionError):
    pass

class Pointer(numeric_region.NumericRegion):
    CASTING_CLASS = None

    def __init__(self, **kwargs):
        self.casting_class = kwargs.setdefault('casting_class', self.CASTING_CLASS)

        if self.casting_class and not issubclass(self.casting_class, memory_region.MemoryRegion):
            raise PointerError('casting class must implement MemoryRegion')
        
        numeric_region.NumericRegion.__init__(self, **kwargs)

    def memory_value(self):
        return self.get_value()

    def deref(self, casting_class=None):
        address_value = self.memory_value()
        
        if casting_class is None:
            casting_class = self.casting_class

        if casting_class is None:
            raise PointerError('no casting class given for dereference')
        
        return casting_class(memory_base=address.Address(offset=address_value))

    def read_pointed_bytes(self, byte_length, byte_offset=0):
        memory_base = address.Address(offset=self.memory_value() + byte_offset)
        region = memory_region.MemoryRegion(memory_base=memory_base
                                            ,bitspan=byte_length*8
                                            ,parent_region=self)
        return region.read_bytes(byte_length)

    def write_pointed_bytes(self, byte_list, byte_offset=0):
        memory_base = address.Address(offset=self.memory_value() + byte_offset)
        region = memory_region.MemoryRegion(memory_base=memory_base
                                            ,bitspan=len(byte_list)*8
                                            ,parent_region=self)
        return region.write_bytes(byte_list)

    def __add__(self, addend):
        if self.casting_class is None:
            raise PointerError('pointer arithmetic not possible without cast')

        value = self.memory_value()
        value += memory_region.sizeof(self.casting_class) * int(addend)

        return self.__class__(value=value, casting_class=self.casting_class)

    def __iadd__(self, addend):
        if self.casting_class is None:
            raise PointerError('pointer arithmetic not possible without cast')

        value = self.memory_value()
        value += memory_region.sizeof(self.casting_class) * int(addend)
        self.set_value(value)

    def __radd__(self, addend):
        return self + int(addend)
    
    def __sub__(self, addend):
        if self.casting_class is None:
            raise PointerError('pointer arithmetic not possible without cast')

        value = self.memory_value()
        value -= memory_region.sizeof(self.casting_class) * int(addend)

        return self.__class__(value=value, casting_class=self.casting_class)

    def __isub__(self, addend):
        if self.casting_class is None:
            raise PointerError('pointer arithmetic not possible without cast')

        value = self.memory_value()
        value -= memory_region.sizeof(self.casting_class) * int(addend)
        self.set_value(value)

    def __rsub__(self, addend):
        if self.casting_class is None:
            raise PointerError('pointer arithmetic not possible without cast')

        value = memory_region.sizeof(self.casting_class) * int(addend)
        value -= self.memory_value()

        return self.__class__(value=value, casting_class=self.casting_class)

    def __getitem__(self, index):
        return (self + index).deref()
    
    @classmethod
    def cast(cls, casting_class):
        class CastedPointer(cls):
            CASTING_CLASS = casting_class

        return CastedPointer

class Pointer32(Pointer):
    BITSPAN = 32

class Pointer64(Pointer):
    BITSPAN = 64
