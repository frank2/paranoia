#!/usr/bin/env python

import ctypes
import inspect
import sys

from paranoia.base.address import Address
from paranoia.base.allocator import heap, Allocator
from paranoia.base.block import BlockChain
from paranoia.base.paranoia_agent import ParanoiaAgent, ParanoiaError
from paranoia.meta.declaration import Declaration
from paranoia.fundamentals import *

try:
    import __builtin__
except ImportError: #python3
    import builtins as __builtin__

__all__ = ['RegionError', 'is_region', 'sizeof', 'Region', 'NumericRegion']

class RegionError(ParanoiaError):
    pass

def is_region(obj):
    return inspect.isclass(obj) and issubclass(obj, Region)

def sizeof(memory_region):
    if is_region(memory_region):
        return memory_region.static_size().byte_length()
    elif isinstance(memory_region, Region):
        return memory_region.size.byte_length()
    elif isinstance(memory_region, Declaration):
        return memory_region.size()
    else:
        raise RegionError('given argument must be a Declaration object or an instance or class deriving Region')
    
class Region(BlockChain):
    DECLARATION = None
    PARENT_REGION = None
    ALIGNMENT = 8
    VALUE = None
    OVERLAPS = False
    SHRINK = False
    VOLATILE = False
    ALIGN_BIT = 1
    ALIGN_BYTE = 8
    ALIGN_BLOCK = 0

    def __init__(self, **kwargs):
        from paranoia.meta.declaration import Declaration

        self.declaration = kwargs.setdefault('declaration', self.DECLARATION)

        if self.declaration is None:
            self.declaration = Declaration(base_class=self.__class__, args=kwargs)
        elif is_region(self.declaration):
            self.declaration = self.declaration.declare(**kwargs)

        if not isinstance(self.declaration, Declaration):
            raise RegionError('declaration must be a Declaration object')
        elif not issubclass(self.declaration.base_class, self.__class__):
            raise RegionError('declaration base_class mismatch')

        self.declaration.instance = self

        self.alignment = kwargs.setdefault('alignment', self.ALIGNMENT)
        self.overlaps = kwargs.setdefault('overlaps', self.OVERLAPS)
        self.parent_region = kwargs.setdefault('parent_region', self.PARENT_REGION)
        self.shrink = kwargs.setdefault('shrink', self.SHRINK)
        self.size = kwargs.setdefault('size', self.SIZE)

        if self.size is None:
            self.size = self.static_size(**kwargs)
            kwargs['size'] = self.size

        self.subregions = dict()
        self.subregion_offsets = dict()
        
        super(Region, self).__init__(**kwargs)

        self.init_finished = False

        value = kwargs.setdefault('value', self.VALUE)
        parse_memory = kwargs.setdefault('parse_memory', self.PARSE_MEMORY)

        if not value is None:
            self.set_value(value)
        elif 'bit_data' in kwargs:
            self.parse_bit_data(kwargs['bit_data'])
        elif 'link_data' in kwargs:
            self.parse_link_data(kwargs['link_data'])
        elif 'block_data' in kwargs:
            self.parse_block_data(kwargs['block_data'])
        elif parse_memory:
            self.parse_memory()

        self.init_finished = True

    def parse_bit_data(self, bit_data):
        parsed = self.declaration.bit_parser(bit_data=bit_data, shift=self.shift)

        if parsed >= self.size:
            self.set_size(parsed)

        self.write_bits(bit_data[:parsed])

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

        self.parse_block_data(block_bytes)

    def set_size(self, new_size):
        if self.is_bound():
            raise RegionError('cannot resize bound region')
        
        if not self.parent_region is None: # subregion
            self.parent_region.resize_subregion(self.declaration, new_size)
            return

        super(Region, self).set_size(new_size)

    def set_value(self, value, force=False):
        raise RegionError('set_value not implemented')

    def get_value(self, force=False):
        raise RegionError('get_value not implemented')

    def rebase(self, new_base, new_shift):
        if not isinstance(new_base, Address):
            raise RegionError('new memory base must be an Address object')

        self.address = new_base
        self.set_shift(new_shift)

        regions = self.subregion_offsets.items()
        regions.sort(lambda x,y: cmp(x[1], y[1]))

        for region in regions:
            ident, offset = region
            decl = self.subregions[ident]
            new_sub_base = self.bit_offset_to_base(offset, decl.alignment())
            new_sub_shift = self.bit_offset_to_shift(offset, decl.alignment())

            if not decl.instance is None:
                decl.instance.rebase(new_sub_base, new_sub_shift)
            else:
                decl.set_arg('address', new_sub_base)
                decl.set_arg('shift', new_sub_shift)

    def subregion_ranges(self):
        regions = self.subregion_offsets.items()
        regions.sort(lambda x,y: cmp(x[1], y[1]))
        result = list()

        for region in regions:
            ident, offset = region
            result.append((offset, offset + int(self.subregions[ident].size())))

        return result

    def in_subregion(self, bit_offset, bitspan, skip_same=False):
        if self.overlaps:
            return False

        if bitspan == 0:
            return False
        
        offsets = self.subregion_ranges()

        for pairing in offsets:
            start, end = pairing

            if skip_same and bit_offset == start:
                continue

            if bit_offset >= start and bit_offset < end:
                return True

            end_region = bit_offset + bitspan

            if end_region > start and end_region <= end:
                return True

        return False

    def next_subregion_offset(self):
        if self.overlaps:
            return 0
        
        offsets = self.subregion_ranges()

        if len(offsets) == 0:
            return 0

        start, end = offsets[-1]
        return end

    def has_subregion(self, decl):
        if not isinstance(decl, Declaration):
            raise RegionError('decl must be a Declaration object')

        return id(decl) in self.subregions

    def declare_subregion(self, decl, bit_offset=None):
        if not isinstance(decl, Declaration):
            raise RegionError('decl must be a Declaration object')

        if self.has_subregion(decl):
            raise RegionError('region already has subregion declaration')
        
        if bit_offset is None:
            bit_offset = align(self.next_subregion_offset(), decl.alignment())
        else:
            bit_offset = align(bit_offset, decl.alignment())
        
        if self.in_subregion(bit_offset, int(decl.size())):
             raise RegionError('subregion declaration overwrites another subregion')

        self.subregions[id(decl)] = decl
        self.subregion_offsets[id(decl)] = bit_offset

        if bit_offset+int(decl.size()) > int(self.size):
            try:
                self.accomodate_subregion(decl, decl.size())
            except Exception as e:
                del self.subregions[id(decl)]
                del self.subregion_offsets[id(decl)]
                raise e

        new_base = self.bit_offset_to_base(bit_offset, decl.alignment())
        new_shift = self.bit_offset_to_shift(bit_offset, decl.alignment())

        if not decl.instance is None:
            decl.instance.rebase(new_base, new_shift)
        else:
            decl.set_arg('address', new_base)
            decl.set_arg('shift', new_shift)

        return decl

    def remove_subregion(self, decl):
        if not isinstance(decl, Declaration):
            raise RegionError('decl must be a Declaration object')

        if not self.has_subregion(decl):
            raise RegionError('no subregion found')
        
        if not decl.instance is None:
            decl.instance.write_bits([0] * decl.bitspan())

        del self.subregion_offsets[id(decl)]
        del self.subregions[id(decl)]

    def move_subregion(self, decl, new_offset):
        if not isinstance(decl, declaration.Declaration):
            raise MemoryRegionError('decl must be a Declaration object')

        if not self.has_subregion(decl):
            raise MemoryRegionError('subregion not found')

        current_offset = self.subregion_offsets[id(decl)]

        if new_offset == current_offset:
            return

        if not decl.instance is None:
            data = decl.instance.read_bits()
        else:
            data = None
        
        self.remove_subregion(decl)
        self.declare_subregion(decl, new_offset)

        if data:
            decl.instance.write_bits(data)

    def accomodate_subregion(self, decl, new_size):
        # called when a subregion wants to resize. this handles e.g. reallocating the memory region
        # if it has been allocated
        if not isinstance(decl, declaration.Declaration):
            raise RegionError('decl must be a Declaration object')

        if not self.has_subregion(decl):
            raise RegionError('subregion not found')

        if not isinstance(new_size, Size):
            raise RegionError('size must be a Size instance')

        current_offset = self.subregion_offsets[id(decl)]

        if self.in_subregion(current_offset, new_size, True):
            raise MemoryRegionError('accomodation overwrites another region')

        new_size = current_offset + int(new_size)

        if new_size <= int(self.size) and not self.shrink:
            return

        self.set_size(Size(bits=new_size))

    def resize_subregion(self, decl, new_size):
        if not isinstance(decl, declaration.Declaration):
            raise RegionError('decl must be a Declaration object')

        if not self.has_subregion(decl):
            raise RegionError('subregion not found')

        if not isinstance(new_size, Size):
            raise RegionError('size must be a Size object')
        
        self.accomodate_subregion(decl, new_size)

        current_offset = self.subregion_offsets[id(decl)]

        self.remove_subregion(decl)

        old_size = decl.size()
        decl.set_arg('size', new_size)

        try:
            self.declare_subregion(decl, current_offset)
        except Exception as e:
            decl.set_arg('size', old_size)
            raise e

        if not decl.instance is None:
            # explicitly call the BlockChain version of this function to prevent
            # an infinite loop
            BlockChain.set_size(decl.instance, new_size)
        
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
        if alignment == Region.ALIGN_BLOCK:
            aligned = align(self.shift + bit_offset, 8)
        else:
            aligned = self.shift + align(bit_offset, alignment)
            
        bytecount = int(aligned/8) # python3 makes a float

        return self.address.fork(bytecount)

    def bit_offset_to_shift(self, bit_offset, alignment):
        if alignment == Region.ALIGN_BLOCK:
            aligned = align(self.shift + bit_offset, 8)
        else:
            aligned = self.shift + align(bit_offset, alignment)

        return aligned % 8

    def read_memory(self):
        return map(int, self.block_iterator())

    @classmethod
    def static_size(cls, **kwargs):
        return cls.SIZE

    @classmethod
    def static_alignment(cls):
        return cls.ALIGNMENT
    
    @classmethod
    def declare(cls, **kwargs):
        return Declaration(base_class=cls, args=kwargs)

    @classmethod
    def bit_parser(cls, **kwargs):
        return kwargs.setdefault('size', cls.SIZE)

    @classmethod
    def subclass(cls, **kwargs):
        kwargs.setdefault('declaration', cls.DECLARATION)
        kwargs.setdefault('parent_region', cls.PARENT_REGION)
        kwargs.setdefault('alignment', cls.ALIGNMENT)
        kwargs.setdefault('value', cls.VALUE)
        kwargs.setdefault('overlaps', cls.OVERLAPS)
        kwargs.setdefault('shrink', cls.SHRINK)
        kwargs.setdefault('volatile', cls.VOLATILE)

        # since BlockChain doesn't support this function, include
        # the arguments it would have
        kwargs.setdefault('address', cls.ADDRESS)
        kwargs.setdefault('allocator', cls.ALLOCATOR)
        kwargs.setdefault('auto_allocate', cls.AUTO_ALLOCATE)
        kwargs.setdefault('shift', cls.SHIFT)
        kwargs.setdefault('buffer', cls.BUFFER)
        kwargs.setdefault('bind', cls.BIND)
        kwargs.setdefault('static', cls.STATIC)
        kwargs.setdefault('maximum_size', cls.MAXIMUM_SIZE)
        kwargs.setdefault('parse_memory', cls.PARSE_MEMORY)

        class SubclassedRegion(cls):
            # Region args
            DECLARATION = kwargs['declaration']
            PARENT_REGION = kwargs['parent_region']
            ALIGNMENT = kwargs['alignment']
            VALUE = kwargs['value']
            OVERLAPS = kwargs['overlaps']
            SHRINK = kwargs['shrink']
            VOLATILE = kwargs['volatile']

            # BlockChain args
            ADDRESS = kwargs['address']
            ALLOCATOR = kwargs['allocator']
            AUTO_ALLOCATE = kwargs['auto_allocate']
            SHIFT = kwargs['shift']
            BUFFER = kwargs['buffer']
            BIND = kwargs['bind']
            STATIC = kwargs['static']
            MAXIMUM_SIZE = kwargs['maximum_size']
            PARSE_MEMORY = kwargs['parse_memory']

        return SubclassedRegion

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

    def get_value(self, force=False):
        value = 0

        links = list(self.link_iterator())

        if self.endianness == self.LITTLE_ENDIAN:
            links.reverse()

        signed_bit = 0
        
        for i in xrange(int(self.size)):
            bit = links[int(i/8)].get_bit(i%8, force)
            
            if i == 0 and self.signage:
                signed_bit = bit
            
            value <<= 1
            value |= bit

        if signed_bit == 1:
            int_max = 2 ** int(self.size)
            value -= int_max

        return value
