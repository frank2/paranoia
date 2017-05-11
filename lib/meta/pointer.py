#!/usr/bin/env python

from paranoia.base import Address, Size
from paranoia.fundamentals import arch
from paranoia.meta.declaration import ensure_declaration
from paranoia.meta.region import RegionDeclaration, RegionError, NumericRegion

__all__ = ['PointerError', 'Pointer', 'LivePointer', 'OffsetError', 'Offset', 'LiveOffset']

class PointerError(RegionError):
    pass

class Pointer(NumericRegion):
    CASTING_DECLARATION = None
    SIZE = Size(bits=arch)

    def __init__(self, **kwargs):
        self.casting_declaration = kwargs.setdefault('casting_declaration', self.CASTING_DECLARATION)

        if not self.casting_declaration is None:
            self.casting_declaration = ensure_declaration(self.casting_declaration)
        
        super(Pointer, self).__init__(**kwargs)

    def memory_value(self):
        return self.get_value()

    def deref(self, casting_decl=None):
        address_value = self.memory_value()
        
        if casting_decl is None:
            casting_decl = self.casting_declaration

        if casting_decl is None:
            raise PointerError('no casting declaration given for dereference')

        casting_decl.set_arg('address', Address(offset=address_value))
        return casting_decl.instantiate()

    def read_pointed_bytes(self, byte_length, byte_offset=0):
        memory_base = Address(offset=self.memory_value() + byte_offset)
        return memory_base.read_bytes(byte_length)

    def write_pointed_bytes(self, byte_list, byte_offset=0):
        memory_base = Address(offset=self.memory_value() + byte_offset)
        memory_base.write_bytes(byte_list)

    def __add__(self, addend):
        if self.casting_declaration is None:
            raise PointerError('pointer arithmetic not possible without cast')

        value = self.memory_value()
        value += self.casting_declaration.size().byte_length() * int(addend)

        return self.__class__(value=value, casting_declaration=self.casting_declaration)

    def __iadd__(self, addend):
        if self.casting_declaration is None:
            raise PointerError('pointer arithmetic not possible without cast')

        value = self.memory_value()
        value += self.casting_declaration.size().byte_length() * int(addend)
        
        self.set_value(value)

    def __radd__(self, addend):
        return self + int(addend)
    
    def __sub__(self, addend):
        if self.casting_declaration is None:
            raise PointerError('pointer arithmetic not possible without cast')

        value = self.memory_value()
        value -= self.casting_declaration.size().byte_length() * int(addend)

        return self.__class__(value=value, casting_declaration=self.casting_declaration)

    def __isub__(self, addend):
        if self.casting_declaration is None:
            raise PointerError('pointer arithmetic not possible without cast')

        value = self.memory_value()
        value -= self.casting_declaration.size().byte_length() * int(addend)
        
        self.set_value(value)

    def __rsub__(self, addend):
        if self.casting_declaration is None:
            raise PointerError('pointer arithmetic not possible without cast')

        value = self.casting_declaration.size().byte_length() * int(addend)
        value -= self.memory_value()

        return self.__class__(value=value, casting_declaration=self.casting_declaration)

    def __getitem__(self, index):
        return (self + index).deref()
    
    @classmethod
    def cast(cls, casting_decl):
        class CastedPointer(cls):
            CASTING_DECLARATION = casting_decl

        return CastedPointer

class LivePointer(Pointer):
    TARGET_DECLARATION = None

    def __init__(self, **kwargs):
        self.target_declaration = kwargs.setdefault('target_declaration', self.TARGET_DECLARATION)

        if self.target_declaration is None:
            raise PointerError('no target declaration given')

        if not isinstance(self.target_declaration, RegionDeclaration):
            raise PointerError('target must be a RegionDeclaration instance')

        super(LivePointer, self).__init__(**kwargs)

    def get_value(self, force=False):
        addr = self.target_declaration.get_arg('address')

        if addr is None:
            raise PointerError('target declaration has no address')
        else:
            value = int(addr)

        self.set_value(value, force)

        return value

    def flush(self):
        self.get_value()
        
        super(LivePointer, self).flush()

class OffsetError(PointerError):
    pass

class Offset(NumericRegion):
    CASTING_DECLARATION = None

    def __init__(self, **kwargs):
        self.casting_declaration = kwargs.setdefault('casting_declaration', self.CASTING_DECLARATION)

        if not self.casting_declaration is None:
            self.casting_declaration = ensure_declaration(self.casting_declaration)
        
        super(Offset, self).__init__(**kwargs)

    def memory_value(self):
        decl = self.declaration

        while not decl.get_arg('parent_declaration') is None:
            decl = decl.get_arg('parent_declaration')

        address = decl.get_arg('address')

        if address is None:
            raise OffsetError('no address in root declaration')

        return address.allocation.id + self.get_value()

    def deref(self, casting_decl=None):
        address_value = self.memory_value()
        
        if casting_decl is None:
            casting_decl = self.casting_declaration

        if casting_decl is None:
            raise OffsetError('no casting declaration given for dereference')

        casting_decl.set_arg('address', Address(offset=address_value))
        return casting_decl.instantiate()

    def read_pointed_bytes(self, byte_length, byte_offset=0):
        memory_base = Address(offset=self.memory_value() + byte_offset)
        return memory_base.read_bytes(byte_length)

    def write_pointed_bytes(self, byte_list, byte_offset=0):
        memory_base = Address(offset=self.memory_value() + byte_offset)
        memory_base.write_bytes(byte_list)

class LiveOffset(Offset):
    TARGET_DECLARATION = None

    def __init__(self, **kwargs):
        self.target_declaration = kwargs.setdefault('target_declaration', self.TARGET_DECLARATION)

        if self.target_declaration is None:
            raise OffsetError('no target declaration given')

        if not isinstance(self.target_declaration, RegionDeclaration):
            raise OffsetError('target must be a RegionDeclaration instance')

        super(LiveOffset, self).__init__(**kwargs)

    def get_value(self, force=False):
        decl = self.target_declaration
        target_addr = decl.get_arg('address')

        if target_addr is None:
            raise OffsetError('target declaration has no address')

        while not decl.get_arg('parent_declaration') is None:
            decl = decl.get_arg('parent_declaration')

        address = decl.get_arg('address')

        if address is None:
            raise PointerError('no address in root declaration')

        addr = self.target_declaration.get_arg('address')
        offset = int(target_addr) - addr.allocation.id

        self.set_value(offset, force)

        return offset

    def flush(self):
        if not self.init_finished:
            return
        
        self.get_value()
        
        super(LiveOffset, self).flush()
