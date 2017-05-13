#!/usr/bin/env python

from paranoia.base import Address, Size
from paranoia.base.event import *
from paranoia.fundamentals import arch
from paranoia.meta.declaration import ensure_declaration
from paranoia.meta.region import RegionDeclarationError, RegionDeclaration, RegionError, NumericRegion

__all__ = ['PointerError', 'Pointer', 'LivePointerDeclarationError'
           ,'LivePointerDeclaration', 'LivePointer', 'OffsetError', 'Offset'
           ,'LiveOffset']

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

class LivePointerDeclarationError(RegionDeclarationError):
    pass

class LivePointerDeclaration(RegionDeclaration):
    def __init__(self, **kwargs):
        super(LivePointerDeclaration, self).__init__(**kwargs)

        args = kwargs.setdefault('args', dict())
        target_decl = args.get('target_declaration')

        if target_decl is None:
            return

        self.set_target_declaration(target_decl)

    def set_target_declaration(self, target_decl):
        if not isinstance(target_decl, RegionDeclaration):
            raise LivePointerDeclarationError('target declaration must be a RegionDeclaration')
        
        self.set_arg('target_declaration', target_decl)
        
        class AddressEventWriter(NewAddressEvent):
            pointer_decl = self
            
            def __call__(self, decl, address, shift):
                self.pointer_decl.write_target_address(address)

        self.event_object = AddressEventWriter()

        target_decl.add_event(self.event_object)

        if not target_decl.get_arg('address') is None:
            self.write_target_address(target_decl.get_arg('address'))

    def write_target_address(self, addr):
        self.set_value(int(addr), True)

    def __del__(self):
        target_decl = self.get_arg('target_declaration')

        if not target_decl is None:
            target_decl.remove_event(self.event_object)
        
class LivePointer(Pointer):
    DECLARATION_CLASS = LivePointerDeclaration
    TARGET_DECLARATION = None

    def __init__(self, **kwargs):
        self.target_declaration = kwargs.setdefault('target_declaration', self.TARGET_DECLARATION)

        super(LivePointer, self).__init__(**kwargs)

    def set_target_declaration(self, target_decl):
        self.declaration.set_target_declaration(target_decl)

LivePointerDeclaration.BASE_CLASS = LivePointer
        
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
        return self.address.allocation.id + self.get_value()

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

class LiveOffsetDeclaration(LivePointerDeclaration):
    def write_target_address(self, address):
        self.set_value(int(address) - address.allocation.id, True)

class LiveOffset(Offset):
    DECLARATION_CLASS = LiveOffsetDeclaration
    TARGET_DECLARATION = None

    def __init__(self, **kwargs):
        self.target_declaration = kwargs.setdefault('target_declaration', self.TARGET_DECLARATION)

        super(LiveOffset, self).__init__(**kwargs)

    def set_target_declaration(self, target_decl):
        self.declaration.set_target_declaration(target_decl)

LiveOffsetDeclaration.BASE_CLASS = LiveOffset
