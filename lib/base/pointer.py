#!/usr/bin/env python

from . import memory_region
from . import numeric_region

class PointerError(numeric_region.NumericRegionError):
    pass

class Pointer(numeric_region.NumericRegion):
    # TODO c-style pointer math
    CASTING_CLASS = None

    def __init__(self, **kwargs):
        self.casting_class = kwargs.setdefault('casting_class', self.CASTING_CLASS)

        if self.casting_class is None:
            raise PointerError('no casting class given to pointer')
        
        if not issubclass(self.casting_class, memory_region.MemoryRegion):
            raise PointerError('casting class must implement MemoryRegion')
        
        numeric_region.NumericRegion.__init__(self, **kwargs)

    def deref(self, casting_class=None):
        address = self.get_value()
        
        if casting_class is None:
            casting_class = self.casting_class

        if casting_class is None:
            raise PointerError('no casting class given for dereference')
        
        return casting_class(memory_base=address)

    def __add__(self, addend):
        if self.casting_class is None:
            raise PointerError('pointer arithmetic not possible without cast')

        value = self.get_value()
        value += memory_region.sizeof(self.casting_class) * int(addend)

        return self.__class__(value=value, casting_class=self.casting_class)

    def __iadd__(self, addend):
        if self.casting_class is None:
            raise PointerError('pointer arithmetic not possible without cast')

        value = self.get_value()
        value += memory_region.sizeof(self.casting_class) * int(addend)
        self.set_value(value)

    def __radd__(self, addend):
        return self + int(addend)
    
    def __sub__(self, addend):
        if self.casting_class is None:
            raise PointerError('pointer arithmetic not possible without cast')

        value = self.get_value()
        value -= memory_region.sizeof(self.casting_class) * int(addend)

        return self.__class__(value=value, casting_class=self.casting_class)

    def __isub__(self, addend):
        if self.casting_class is None:
            raise PointerError('pointer arithmetic not possible without cast')

        value = self.get_value()
        value -= memory_region.sizeof(self.casting_class) * int(addend)
        self.set_value(value)

    def __rsub__(self, addend):
        if self.casting_class is None:
            raise PointerError('pointer arithmetic not possible without cast')

        value = memory_region.sizeof(self.casting_class) * int(addend)
        value -= self.get_value()

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
