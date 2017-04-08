#!/usr/bin/env python

from paranoia.base import address, declaration, memory_region, numeric_region

__all__ = ['PointerError', 'Pointer', 'Pointer32', 'Pointer64']

class PointerError(numeric_region.NumericRegionError):
    pass

class Pointer(numeric_region.NumericRegion):
    CASTING_DECLARATION = None

    def __init__(self, **kwargs):
        self.casting_declaration = kwargs.setdefault('casting_declaration', self.CASTING_DECLARATION)

        if not self.casting_declaration is None:
            self.casting_declaration = memory_region.ensure_declaration(self.casting_declaration)
        
        numeric_region.NumericRegion.__init__(self, **kwargs)

    def memory_value(self):
        return self.get_value()

    def deref(self, casting_decl=None):
        address_value = self.memory_value()
        
        if casting_decl is None:
            casting_decl = self.casting_declaration

        if casting_decl is None:
            raise PointerError('no casting declaration given for dereference')

        casting_decl.set_arg('memory_base', address.Address(offset=address_value))
        return casting_decl.copy().instantiate()

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
        if self.casting_declaration is None:
            raise PointerError('pointer arithmetic not possible without cast')

        value = self.memory_value()
        value += memory_region.sizeof(self.casting_declaration) * int(addend)

        return self.__class__(value=value, casting_declaration=self.casting_declaration)

    def __iadd__(self, addend):
        if self.casting_declaration is None:
            raise PointerError('pointer arithmetic not possible without cast')

        value = self.memory_value()
        value += memory_region.sizeof(self.casting_declaration) * int(addend)
        self.set_value(value)

    def __radd__(self, addend):
        return self + int(addend)
    
    def __sub__(self, addend):
        if self.casting_declaration is None:
            raise PointerError('pointer arithmetic not possible without cast')

        value = self.memory_value()
        value -= memory_region.sizeof(self.casting_declaration) * int(addend)

        return self.__class__(value=value, casting_declaration=self.casting_declaration)

    def __isub__(self, addend):
        if self.casting_declaration is None:
            raise PointerError('pointer arithmetic not possible without cast')

        value = self.memory_value()
        value -= memory_region.sizeof(self.casting_declaration) * int(addend)
        self.set_value(value)

    def __rsub__(self, addend):
        if self.casting_declaration is None:
            raise PointerError('pointer arithmetic not possible without cast')

        value = memory_region.sizeof(self.casting_declaration) * int(addend)
        value -= self.memory_value()

        return self.__class__(value=value, casting_declaration=self.casting_declaration)

    def __getitem__(self, index):
        return (self + index).deref()
    
    @classmethod
    def cast(cls, casting_decl):
        class CastedPointer(cls):
            CASTING_DECLARATION = casting_decl

        return CastedPointer

class Pointer32(Pointer):
    BITSPAN = 32

class Pointer64(Pointer):
    BITSPAN = 64
