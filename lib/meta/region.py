#!/usr/bin/env python

import ctypes
import inspect
import sys

from paranoia.base.address import Address
from paranoia.base.block import Block, BlockChain
from paranoia.base.event import *
from paranoia.base.paranoia_agent import ParanoiaAgent, ParanoiaError
from paranoia.meta.declaration import Declaration, DeclarationError
from paranoia.fundamentals import *

try:
    import __builtin__
except ImportError: #python3
    import builtins as __builtin__

__all__ = ['RegionError', 'is_region', 'sizeof', 'RegionDeclarationError'
           ,'RegionDeclaration', 'Region', 'NumericRegion']

def is_region(obj):
    return inspect.isclass(obj) and issubclass(obj, Region)

def sizeof(memory_region):
    if is_region(memory_region):
        return memory_region.static_size().byte_length()
    elif isinstance(memory_region, Region):
        return memory_region.size.byte_length()
    elif isinstance(memory_region, RegionDeclaration):
        return memory_region.size()
    else:
        raise RegionError('given argument must be a RegionDeclaration object or an instance or class deriving Region')

class RegionDeclarationError(DeclarationError):
    pass
 
class RegionDeclaration(Declaration): # BASE_CLASS set to Region after Region definition
    def __init__(self, **kwargs):
        super(RegionDeclaration, self).__init__(**kwargs)

        self.subregions = dict()
        self.subregion_offsets = dict()
        self.reverse_offsets = dict()
        self.current_offsets = set()

    def set_address(self, address, shift=None):
        if self.instance is None:
            self.set_arg('address', address)
        else:
            BlockChain.set_address(self.instance, address)

        if not shift is None:
            self.set_shift(shift)

        self.trigger_event(NewAddressEvent, address, shift)

    def set_shift(self, shift):
        if self.instance is None:
            self.set_arg('shift', shift)
        else:
            self.instance.set_shift(shift)

        self.trigger_event(NewShiftEvent, shift)

    def set_size(self, size):
        parent_decl = self.get_arg('parent_declaration')

        old_size = self.get_arg('size')

        if not self.instance is None:
            # call the BlockChain version of the function to prevent an infinite
            # loop
            old_address = int(self.instance.address)
            BlockChain.set_size(self.instance, size)
            new_address = int(self.instance.address)

            if not old_address == new_address: # chain moved, rebase
                self.rebase(self.instance.address, self.get_arg('shift'))
        else:
            self.set_arg('size', size)
        
        self.trigger_event(NewSizeEvent, old_size, size)

    def is_bound(self):
        return self.get_arg('bind') and self.get_arg('init_finished')

    def is_static(self):
        return self.get_arg('static') and self.get_arg('init_finished')

    def align(self, offset, shift):
        alignment = self.get_arg('alignment')

        if alignment == self.base_class.ALIGN_BLOCK:
            return align(offset + shift, 8)
        else:
            return shift + align(offset, alignment)

    def size(self, **kwargs):
        size = self.get_arg('size')

        if size is None or int(size) == 0:
            size = self.base_class.static_size(**kwargs)

        return size

    def declarative_size(self, **kwargs):
        return self.size(**kwargs)

    def bit_parser(self, **kwargs):
        dict_merge(kwargs, self.args)

        kwargs['declaration'] = self
        
        return self.base_class.bit_parser(**kwargs)

    def get_value(self, **kwargs):
        if not self.instance is None:
            force = kwargs.setdefault('force', False)
            return self.instance.get_value(force)
        
        value = self.get_arg('value')

        if value is None:
            dict_merge(kwargs, self.args)
            value = self.base_class.static_value(**kwargs)

        return value

    def set_value(self, value, force=False):
        if not self.instance is None:
            return self.instance.set_value(value, force)

        self.set_arg('value', value)

        self.trigger_event(SetValueEvent, value)

    def rebase(self, new_base, new_shift):
        if not isinstance(new_base, Address):
            raise RegionError('new memory base must be an Address object')

        self.set_address(new_base, new_shift)

        for decl_id in self.subregions:
            decl = self.subregions[decl_id]
            offset = self.subregion_offsets[decl_id]
            base = self.bit_offset_to_base(offset, decl.get_arg('alignment'))
            shift = self.bit_offset_to_shift(offset, decl.get_arg('alignment'))

            decl.rebase(base, shift)

    def subregion_ranges(self):
        result = list()

        for offset in self.current_offsets:
            reverse_offset = self.reverse_offsets[offset]

            for ident in reverse_offset:
                region = self.subregions[ident]
                result.append((offset, offset + int(region.size())))

        return result

    def in_subregion(self, bit_offset, bitspan, skip_same=False):
        overlaps = self.get_arg('overlaps')
        
        if overlaps:
            return False

        if bitspan == 0:
            return False

        if bit_offset in self.reverse_offsets and not skip_same:
            return True

        for start in self.current_offsets:
            if skip_same and bit_offset == start:
                continue
            
            for offset_ident in self.reverse_offsets[start]:
                end = start + int(self.subregions[offset_ident].size())

                if bit_offset >= start and bit_offset < end:
                    return True

                end_region = bit_offset + bitspan

                if end_region > start and end_region <= end:
                    return True

        return False

    def next_subregion_offset(self):
        overlaps = self.get_arg('overlaps')
        
        if overlaps:
            return 0

        if len(self.current_offsets) == 0:
            return 0

        start = max(self.current_offsets)
        end = start + max(map(lambda x: int(x.size()), self.reverse_offsets[start]))
        return end

    def has_subregion(self, decl):
        if not isinstance(decl, RegionDeclaration):
            raise RegionDeclarationError('decl must be a RegionDeclaration object')

        return id(decl) in self.subregions

    def declare_subregion(self, decl, bit_offset=None):
        if not isinstance(decl, RegionDeclaration):
            raise RegionDeclarationError('decl must be a RegionDeclaration object')

        if self.has_subregion(decl):
            raise RegionDeclarationError('region already has subregion declaration')

        shift = self.get_arg('shift')
        
        if bit_offset is None:
            bit_offset = decl.align(self.next_subregion_offset(), shift)
        else:
            bit_offset = decl.align(bit_offset, shift)

        if self.in_subregion(bit_offset, int(decl.size())):
             raise RegionDeclarationError('subregion declaration overwrites another subregion')

        self.subregions[id(decl)] = decl
        self.subregion_offsets[id(decl)] = bit_offset
        self.reverse_offsets.setdefault(bit_offset, list()).append(id(decl))
        self.current_offsets.add(bit_offset)

        if bit_offset+int(decl.size()) > int(self.size()):
            raise RegionDeclarationError('declaration exceeds region size')
        
        if not self.get_arg('address') is None:
            new_base = self.bit_offset_to_base(bit_offset, decl.get_arg('alignment'))
        else:
            new_base = None
            
        new_shift = self.bit_offset_to_shift(bit_offset, decl.get_arg('alignment'))

        if not new_base is None:
            decl.rebase(new_base, new_shift)
        else:
            decl.set_shift(new_shift)
            
        decl.set_arg('parent_declaration', self)

        resize_event = self.get_arg('resize_event')

        if inspect.isclass(resize_event) and issubclass(resize_event, NewSizeEvent):
            new_event = resize_event()
            self.set_arg('resize_event', new_event)
            resize_event = new_event

        if not isinstance(resize_event, NewSizeEvent):
            raise RegionDeclarationError('resize event must be a NewSizeEvent')

        decl.add_event(resize_event)

        self.trigger_event(DeclareSubregionEvent, decl)

        return decl

    def remove_subregion(self, decl):
        if not isinstance(decl, RegionDeclaration):
            raise RegionDeclarationError('decl must be a Declaration object')

        if not self.has_subregion(decl):
            raise RegionDeclarationError('no subregion found')

        self.trigger_event(RemoveSubregionEvent, decl)

        if not decl.instance is None:
            decl.instance.write_bits([0] * int(decl.size()))

        offset = self.subregion_offsets[id(decl)]
        self.reverse_offsets[offset].remove(id(decl))

        if len(self.reverse_offsets[offset]) == 0:
            del self.reverse_offsets[offset]

        self.current_offsets.remove(offset)
        del self.subregion_offsets[id(decl)]
        del self.subregions[id(decl)]
        
        if 'parent_declaration' in decl.args:
            del decl.args['parent_declaration']

        if 'address' in decl.args:
            del decl.args['address']

        if 'shift' in decl.args:
            del decl.args['shift']

        decl.remove_event(self.get_arg('resize_event'))

    def move_subregion(self, decl, new_offset):
        if not isinstance(decl, RegionDeclaration):
            raise RegionDeclarationError('decl must be a Declaration object')

        if not self.has_subregion(decl):
            raise RegionDeclarationError('subregion not found')

        current_offset = self.subregion_offsets[id(decl)]

        if new_offset == current_offset:
            return
        
        if not decl.instance is None:
            data = decl.instance.read_bits()
            decl.instance.write_bits([0] * int(decl.size()))
        else:
            data = None

        self.reverse_offsets[current_offset].remove(id(decl))

        if len(self.reverse_offsets[current_offset]) == 0:
            del self.reverse_offsets[current_offset]

        self.current_offsets.remove(current_offset)

        if not self.get_arg('address') is None:
            new_base = self.bit_offset_to_base(new_offset, decl.get_arg('alignment'))
            new_shift = self.bit_offset_to_shift(new_offset, decl.get_arg('alignment'))
        else:
            new_base = None
            new_shift = None

        self.subregion_offsets[id(decl)] = new_offset
        self.reverse_offsets.setdefault(new_offset, list()).append(id(decl))
        self.current_offsets.add(new_offset)

        if not new_base is None:
            decl.rebase(new_base, new_shift)

        if data:
            decl.instance.write_bits(data)

        self.trigger_event(MoveSubregionEvent, current_offset, new_offset)
        
    def push_subregions(self, decl, delta, include=False):
        if not isinstance(decl, RegionDeclaration):
            raise RegionDeclarationError('decl must be a Declaration object')

        if not self.has_subregion(decl):
            raise RegionDeclarationError('subregion not found')

        if self.get_arg('overlaps'):
            return

        decl_offset = self.subregion_offsets[id(decl)]
        move_ops = list()
        shift = self.get_arg('shift')
        shrink = self.get_arg('shrink')
        ranges = self.subregion_ranges()
        index = 0

        for index in xrange(len(ranges)):
            if not include and index > 0 and ranges[index-1][0] == decl_offset:
                break
            elif include and ranges[index][0] == decl_offset:
                break

        if not include and index == len(ranges)-1:
            return

        if include:
            offset = decl.align(decl_offset+delta, shift)
            new_ranges = {index: (offset, int(decl.size()+offset))}
            move_ops.append((decl, offset))
            index += 1
        else:
            new_ranges = {index-1: (ranges[index-1][0], ranges[index-1][1]+delta)}
            
        while index < len(ranges):
            if index == 0:
                prev_range = (0, 0)
            else:
                prev_range = new_ranges[index-1]
                
            curr_range = ranges[index]
            curr_start, curr_end = curr_range
            prev_start, prev_end = prev_range
            curr_ident = self.reverse_offsets[curr_start][0]
            curr_decl = self.subregions[curr_ident]

            if delta > 0 and prev_end > curr_start or shrink and delta < 0:
                delta = prev_end - curr_start
                new_offset = curr_decl.align(curr_start+delta, shift)

                if delta > 0:
                    move_ops.append((curr_decl, new_offset))
                else:
                    move_ops.insert(0, (curr_decl, new_offset))
                    
                new_ranges[index] = (new_offset, new_offset+int(curr_decl.size()))
            else:
                break

            index += 1

        while len(move_ops):
            op = move_ops.pop()
            decl, offset = op
            self.move_subregion(decl, offset)

    def bit_offset_subregions(self, bit_offset):
        current_offsets = self.subregion_offsets.items()
        current_offsets = filter(lambda x: x == bit_offset, current_offsets)
        
        if len(current_offsets):
            return map(lambda x: self.subregions[x], current_offsets)

        results = list()
        
        for ident in self.subregions:
            subregion = self.subregions[ident]
            ident_offset = self.subregion_offsets[ident]

            if bit_offset >= ident_offset and bit_offset < ident_offset+int(subregion.size()):
                results.append(ident)

        if len(results):
            return map(lambda x: self.subregions[x], results)

    def bit_offset_to_base(self, bit_offset, alignment):
        address = self.get_arg('address')

        if address is None:
            raise RegionDeclarationError('no address to fork from')
        
        shift = self.get_arg('shift')
        
        if alignment == Region.ALIGN_BLOCK:
            aligned = align(shift + bit_offset, 8)
        else:
            aligned = shift + align(bit_offset, alignment)
            
        bytecount = int(aligned/8) # python3 makes a float
        return address.fork(bytecount)

    def bit_offset_to_shift(self, bit_offset, alignment):
        shift = self.get_arg('shift')
        
        if alignment == Region.ALIGN_BLOCK:
            aligned = align(shift + bit_offset, 8)
        else:
            aligned = shift + align(bit_offset, alignment)

        return aligned % 8

class RegionError(ParanoiaError):
    pass

class RegionResizeEvent(NewSizeEvent):
    def __call__(self, decl, old_size, new_size):
        delta = int(new_size) - int(old_size)

        if delta == 0:
            return
        
        parent_decl = decl.get_arg('parent_declaration')
        parent_decl.push_subregions(decl, delta)

class Region(BlockChain):
    DECLARATION_CLASS = RegionDeclaration
    RESIZE_EVENT = RegionResizeEvent
    DECLARATION = None
    PARENT_DECLARATION = None
    ALIGNMENT = 8
    VALUE = None
    OVERLAPS = False
    SHRINK = False
    ALIGN_BIT = 1
    ALIGN_BYTE = 8
    ALIGN_BLOCK = 0

    def __init__(self, **kwargs):
        self.declaration_class = kwargs.setdefault('declaration_class', self.DECLARATION_CLASS)
        self.declaration = kwargs.setdefault('declaration', self.DECLARATION)

        if self.declaration is None:
            if self.declaration_class is None:
                raise RegionError('both declaration and declaration_class cannot be None')
            
            self.declaration = self.declaration_class(base_class=self.__class__
                                                      ,args=kwargs)
            kwargs = self.declaration.args
        elif is_region(self.declaration):
            self.declaration = self.declaration.declare(**kwargs)
            kwargs = self.declaration.args

        if not isinstance(self.declaration, Declaration):
            raise RegionError('declaration must be a Declaration object')
        elif not issubclass(self.declaration.base_class, self.__class__):
            raise RegionError('declaration base_class mismatch')

        self.declaration.set_instance(self)
        dict_merge(kwargs, self.declaration.args)

        resize_event = kwargs.setdefault('resize_event', self.RESIZE_EVENT)

        if inspect.isclass(resize_event) and issubclass(resize_event, NewSizeEvent):
            self.resize_event = resize_event()
        elif not isinstance(resize_event, NewSizeEvent):
            raise RegionError('resize event must be a class or instance of NewSizeEvent')
            
        self.alignment = kwargs.setdefault('alignment', self.ALIGNMENT)
        self.overlaps = kwargs.setdefault('overlaps', self.OVERLAPS)
        self.parent_declaration = kwargs.setdefault('parent_declaration', self.PARENT_DECLARATION)
        self.shrink = kwargs.setdefault('shrink', self.SHRINK)
        self.size = kwargs.setdefault('size', self.SIZE)

        if self.size is None or self.size == 0:
            self.size == self.declaration.declarative_size()

        super(Region, self).__init__(**kwargs)

        self.init_finished = False

        value = kwargs.setdefault('value', self.VALUE)
        parse_memory = kwargs.setdefault('parse_memory', self.PARSE_MEMORY)

        if 'bit_data' in kwargs:
            self.parse_bit_data(kwargs['bit_data'])
        elif 'link_data' in kwargs:
            self.parse_link_data(kwargs['link_data'])
        elif 'block_data' in kwargs:
            self.parse_block_data(kwargs['block_data'])
        elif parse_memory:
            self.parse_memory()
        elif not value is None:
            self.set_value(value)

        self.init_finished = True

        # rebase the declaration to our new address
        self.declaration.rebase(self.address, self.shift)

    def set_address(self, address, shift=None):
        if not self.init_finished:
            super(Region, self).set_address(address, shift)
            return
        
        if shift is None:
            shift = self.shift
            
        self.declaration.rebase(address, shift)

    def set_size(self, size):
        if not self.init_finished:
            super(Region, self).set_size(size)
            return
        
        self.declaration.set_size(size)

    def parse_bit_data(self, bit_data):
        parsed = self.declaration.bit_parser(bit_data=bit_data)
        
        if parsed > self.size:
            self.set_size(parsed)

        self.write_bits(bit_data[:int(parsed)])
        self.flush()

        return parsed

    def parse_link_data(self, link_data):
        if isinstance(link_data, str):
            link_data = map(ord, link_data)

        bit_list = bytelist_to_bitlist(link_data)

        return self.parse_bit_data(bit_list)

    def parse_block_data(self, block_data):
        if isinstance(block_data, str):
            block_data = map(ord, block_data)

        block_bits = bytelist_to_bitlist(block_data)

        return self.parse_bit_data(block_bits[self.shift:])

    def parse_memory(self):
        block_bytes = list()

        for block in self.block_iterator():
            block_bytes.append(block.get_value(force=True))

        return self.parse_block_data(block_bytes)

    def set_value(self, value, force=False):
        raise RegionError('set_value not implemented')

    def get_value(self, force=False):
        raise RegionError('get_value not implemented')

    def read_memory(self):
        return map(int, self.block_iterator())

    def __setattr__(self, attr, value):
        if 'declaration' in self.__dict__ and not self.__dict__['declaration'] is None:
            self.__dict__['declaration'].set_arg(attr, value, True)

        super(Region, self).__setattr__(attr, value)

    def __del__(self):
        self.declaration.instance = None
        super(Region, self).__del__()

    @classmethod
    def static_size(cls, **kwargs):
        return cls.SIZE

    @classmethod
    def static_value(cls, **kwargs):
        raise RegionError('static_value not implemented')
    
    @classmethod
    def declare(cls, **kwargs):
        declaration_class = kwargs.setdefault('declaration_class', cls.DECLARATION_CLASS)

        if declaration_class is None:
            raise RegionError('declaration class cannot be None')
        
        return declaration_class(base_class=cls, args=kwargs)

    @classmethod
    def bit_parser(cls, **kwargs):
        size = kwargs.setdefault('size', cls.SIZE)

        if size is None or size == 0:
            size = cls.static_size(**kwargs)

        return size

    @classmethod
    def subclass(cls, **kwargs):
        kwargs.setdefault('declaration_class', cls.DECLARATION_CLASS)
        kwargs.setdefault('declaration', cls.DECLARATION)
        kwargs.setdefault('parent_declaration', cls.PARENT_DECLARATION)
        kwargs.setdefault('alignment', cls.ALIGNMENT)
        kwargs.setdefault('value', cls.VALUE)
        kwargs.setdefault('overlaps', cls.OVERLAPS)
        kwargs.setdefault('shrink', cls.SHRINK)

        # since BlockChain doesn't support this function, include
        # the arguments it would have
        kwargs.setdefault('address', cls.ADDRESS)
        kwargs.setdefault('allocator', cls.ALLOCATOR)
        kwargs.setdefault('auto_allocate', cls.AUTO_ALLOCATE)
        kwargs.setdefault('size', cls.SIZE)
        kwargs.setdefault('shift', cls.SHIFT)
        kwargs.setdefault('buffer', cls.BUFFER)
        kwargs.setdefault('bind', cls.BIND)
        kwargs.setdefault('static', cls.STATIC)
        kwargs.setdefault('maximum_size', cls.MAXIMUM_SIZE)
        kwargs.setdefault('parse_memory', cls.PARSE_MEMORY)

        class SubclassedRegion(cls):
            # Region args
            DECLARATION_CLASS = kwargs['declaration_class']
            DECLARATION = kwargs['declaration']
            PARENT_DECLARATION = kwargs['parent_declaration']
            ALIGNMENT = kwargs['alignment']
            VALUE = kwargs['value']
            OVERLAPS = kwargs['overlaps']
            SHRINK = kwargs['shrink']

            # BlockChain args
            ADDRESS = kwargs['address']
            ALLOCATOR = kwargs['allocator']
            AUTO_ALLOCATE = kwargs['auto_allocate']
            SIZE = kwargs['size']
            SHIFT = kwargs['shift']
            BUFFER = kwargs['buffer']
            BIND = kwargs['bind']
            STATIC = kwargs['static']
            MAXIMUM_SIZE = kwargs['maximum_size']
            PARSE_MEMORY = kwargs['parse_memory']

        return SubclassedRegion

RegionDeclaration.BASE_CLASS = Region

class NumericRegion(Region):
    ENDIANNESS = 0
    SIGNAGE = 0
    LITTLE_ENDIAN = 0
    BIG_ENDIAN = 1
    UNSIGNED = 0
    SIGNED = 1

    def __init__(self, **kwargs):
        self.endianness = kwargs.setdefault('endianness', self.ENDIANNESS)

        if not self.endianness == self.LITTLE_ENDIAN and not self.endianness == self.BIG_ENDIAN:
            raise RegionError('endianness must be NumericRegion.LITTLE_ENDIAN or NumericRegion.BIG_ENDIAN')

        self.signage = kwargs.setdefault('signage', self.SIGNAGE)

        if not self.signage == self.UNSIGNED and not self.signage == self.SIGNED:
            raise RegionError('signage must be NumericRegion.SIGNED or NumericRegion.UNSIGNED')

        super(NumericRegion, self).__init__(**kwargs)

    def set_value(self, value, force=False):
        int_max = 2 ** int(self.size)

        value_push = value

        if abs(value) >= int_max:
            raise RegionError('integer overflow')

        if value < 0:
            # convert the negative number into two's compliment
            value += int_max

            if value < 0:
                raise RegionError('negative overflow')

        if value >= int_max:
            raise RegionError('integer overflow')

        self.declaration.set_arg('value', value)
        
        value_bits = list()
            
        for i in xrange(int(self.size)):
            value_bits.append(value & 1)
            value >>= 1

        value_bits.reverse()

        links = list(self.link_iterator())

        if self.endianness == self.LITTLE_ENDIAN:
            links.reverse()

        for i in xrange(int(self.size)):
            links[int(i/8)].set_bit(i % 8, value_bits[i], force)

        if not force and not self.buffer:
            self.flush()

        self.declaration.set_arg('value', value_push)
        self.declaration.trigger_event(SetValueEvent, value_push)

    def get_value(self, force=False):
        kwargs = dict()
        kwargs['link_data'] = map(lambda x: x.get_value(force), self.link_iterator())
        dict_merge(kwargs, self.declaration.args)
        
        return self.static_value(**kwargs)

    def __int__(self):
        return self.get_value()

    def __cmp__(self, other):
        return cmp(self.get_value(), int(other))

    def __add__(self, other):
        if not isinstance(other, (int, NumericRegion)):
            raise RegionError('addend must be an int or another NumericRegion')

        return self.get_value() + other

    def __radd__(self, other):
        return self + other

    def __iadd__(self, other):
        self.set_value(self + other)

    def __sub__(self, other):
        if not isinstance(other, (int, NumericRegion)):
            raise RegionError('subtractor must be an int or another NumericRegion')

        return self.get_value() - other

    def __rsub__(self, other):
        if not isinstance(other, (int, NumericRegion)):
            raise RegionError('subtractor must be an int or another NumericRegion')

        return other - self.get_value()

    def __isub__(self, other):
        self.set_value(self - other)

    def __mul__(self, other):
        if not isinstance(other, (int, NumericRegion)):
            raise RegionError('multiplicant must be an int or another NumericRegion')

        return self.get_value() * other

    def __rmul__(self, other):
        return self * other

    def __imul__(self, other):
        self.set_value(self * other)

    def __div__(self, other):
        if not isinstance(other, (int, NumericRegion)):
            raise RegionError('divisor must be an int or another NumericRegion')

        return self.get_value() / other

    def __rdiv__(self, other):
        if not isinstance(other, (int, NumericRegion)):
            raise RegionError('divisor must be an int or another NumericRegion')

        return other / self.get_value()

    def __idiv__(self, other):
        self.set_value(self / other)

    def __mod__(self, other):
        if not isinstance(other, (int, NumericRegion)):
            raise RegionError('modulus must be an int or another NumericRegion')

        return self.get_value() % other

    def __rmod__(self, other):
        if not isinstance(other, (int, NumericRegion)):
            raise RegionError('modulus must be an int or another NumericRegion')

        return other % self.get_value()

    def __imod__(self, other):
        self.set_value(self % other)

    def __pow__(self, exponent):
        if not isinstance(exponent, (int, NumericRegion)):
            raise RegionError('exponent must be an int or another NumericRegion')

        return self.get_value() ** exponent

    def __rpow__(self, exponent):
        if not isinstance(exponent, (int, NumericRegion)):
            raise RegionError('exponent must be an int or another NumericRegion')

        return exponent ** self.get_value()

    def __ipow__(self, exponent):
        self.set_value(self ** exponent)

    def __lshift__(self, shift):
        if not isinstance(exponent, (int, NumericRegion)):
            raise RegionError('shift must be an int or another NumericRegion')

        return self.get_value() << shift

    def __rlshift__(self, shift):
        if not isinstance(exponent, (int, NumericRegion)):
            raise RegionError('shift must be an int or another NumericRegion')

        return shift << self.get_value()

    def __ilshift__(self, shift):
        self.set_value((self.get_value() << shift) & ((2 ** int(self.size)) - 1))

    def __rshift__(self, shift):
        if not isinstance(exponent, (int, NumericRegion)):
            raise RegionError('shift must be an int or another NumericRegion')

        return self.get_value() >> shift

    def __rrshift__(self, shift):
        if not isinstance(exponent, (int, NumericRegion)):
            raise RegionError('shift must be an int or another NumericRegion')

        return shift >> self.get_value()

    def __irshift__(self, shift):
        self.set_value(self.get_value() >> shift)

    def __and__(self, other):
        if not isinstance(other, (int, NumericRegion)):
            raise RegionError('logical value must be an int or another NumericRegion')

        return self.get_value() & other

    def __rand__(self, other):
        if not isinstance(other, (int, NumericRegion)):
            raise RegionError('logical value must be an int or another NumericRegion')

        return other & self.get_value()

    def __iand__(self, other):
        self.set_value(self & other)

    def __or__(self, other):
        if not isinstance(other, (int, NumericRegion)):
            raise RegionError('logical value must be an int or another NumericRegion')

        return self.get_value() | other

    def __ror__(self, other):
        if not isinstance(other, (int, NumericRegion)):
            raise RegionError('logical value must be an int or another NumericRegion')

        return other | self.get_value()

    def __ior__(self, other):
        self.set_value(self | other)

    def __xor__(self, other):
        if not isinstance(other, (int, NumericRegion)):
            raise RegionError('logical value must be an int or another NumericRegion')

        return self.get_value() ^ other

    def __rxor__(self, other):
        if not isinstance(other, (int, NumericRegion)):
            raise RegionError('logical value must be an int or another NumericRegion')

        return other ^ self.get_value()

    def __ixor__(self, other):
        self.set_value(self ^ other)

    def __neg__(self):
        return -self.get_value()

    def __pos__(self):
        return +self.get_value()

    def __abs__(self):
        return abs(self.get_value())

    def __invert__(self):
        return ~self.get_value()

    def __oct__(self):
        return oct(self.get_value())

    def __hex__(self):
        return hex(self.get_value())
    
    @classmethod
    def static_value(cls, **kwargs):
        if 'bit_data' in kwargs:
            bit_data = kwargs['bit_data']
            bit_data += [0] * (8 - len(bit_data))
            links = map(lambda x: Block(value=x), bitlist_to_bytelist(bit_data))
        elif 'link_data' in kwargs:
            links = map(lambda x: Block(value=x), kwargs['link_data'])
        elif 'block_data' in kwargs:
            bit_data = bytelist_to_bitlist(kwargs['block_data'])
            shift = kwargs.setdefault('shift', cls.SHIFT)
            bit_data = bit_data[shift:]
            links = map(lambda x: Block(value=x), bitlist_to_bytelist(bit_data))
        else:
            raise RegionError('no data to parse')

        value = 0
        endianness = kwargs.setdefault('endianness', cls.ENDIANNESS)
        size = kwargs.setdefault('size', cls.SIZE)
        signage = kwargs.setdefault('signage', cls.SIGNAGE)

        if endianness == cls.LITTLE_ENDIAN:
            links.reverse()

        signed_bit = 0
        
        for i in xrange(int(size)):
            bit = links[int(i/8)].get_bit(i%8)
            
            if i == 0 and signage:
                signed_bit = bit
            
            value <<= 1
            value |= bit

        if signed_bit == 1:
            int_max = 2 ** int(size)
            value -= int_max

        return value
