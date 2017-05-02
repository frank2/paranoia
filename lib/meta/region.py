#!/usr/bin/env python

import ctypes
import inspect
import sys

from paranoia.base.address import Address
from paranoia.base.allocator import heap, Allocator
from paranoia.base.block import Block, BlockChain
from paranoia.base.paranoia_agent import ParanoiaAgent, ParanoiaError
from paranoia.meta.declaration import Declaration, DeclarationError, ensure_declaration
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
    elif isinstance(memory_region, Declaration):
        return memory_region.size()
    else:
        raise RegionError('given argument must be a Declaration object or an instance or class deriving Region')

class RegionDeclarationError(DeclarationError):
    pass
 
class RegionDeclaration(Declaration): # BASE_CLASS set to Region after Region definition
    def __init__(self, **kwargs):
        super(RegionDeclaration, self).__init__(**kwargs)

        self.subregions = dict()
        self.subregion_offsets = dict()

    def set_address(self, address):
        if self.instance is None:
            self.set_arg('address', address)
        else:
            BlockChain.set_address(self.instance, address)

    def set_shift(self, shift):
        if self.instance is None:
            self.set_arg('shift', shift)
        else:
            self.instance.set_shift(shift)

    def set_size(self, size):
        parent_decl = self.get_arg('parent_declaration')
        
        if not parent_decl is None and id(self) in parent_decl.subregions:
            parent_decl.resize_subregion(self, size)
            return
        
        if not self.instance is None:
            # call the BlockChain version of the function to prevent an infinite
            # loop
            BlockChain.set_size(self.instance, size)
            return

        self.set_arg('size', size)

    def align(self, offset, shift):
        alignment = self.get_arg('alignment')

        if alignment == self.base_class.ALIGN_BLOCK:
            return align(offset + shift, 8)
        else:
            return shift + align(offset, alignment)

    def size(self, **kwargs):
        dict_merge(kwargs, self.args)
        
        size = self.get_arg('size')

        if size is None or int(size) == 0:
            return self.base_class.static_size(**kwargs)

        return size

    def bit_parser(self, **kwargs):
        dict_merge(kwargs, self.args)

        return self.base_class.bit_parser(**kwargs)

    def get_value(self, **kwargs):
        if not self.instance is None:
            force = kwargs.setdefault('force', False)
            return self.instance.get_value(force)
        
        value = self.get_arg('value')

        if value is None:
            dict_merge(kwargs, self.args)
            return self.base_class.static_value(**kwargs)

        return value

    def set_value(self, value, force=False):
        if not self.instance is None:
            return self.instance.set_value(value, force)

        self.set_arg('value', value)

    def rebase(self, new_base, new_shift):
        if not isinstance(new_base, Address):
            raise RegionError('new memory base must be an Address object')

        self.set_address(new_base)
        self.set_shift(new_shift)

        regions = self.subregion_offsets.items()
        regions.sort(lambda x,y: cmp(x[1], y[1]))

        for region in regions:
            ident, offset = region
            decl = self.subregions[ident]

            new_sub_base = self.bit_offset_to_base(offset, decl.get_arg('alignment'))
            new_sub_shift = self.bit_offset_to_shift(offset, decl.get_arg('alignment'))

            decl.rebase(new_sub_base, new_sub_shift)

    def subregion_ranges(self):
        regions = self.subregion_offsets.items()
        regions.sort(lambda x,y: cmp(x[1], y[1]))
        result = list()

        for region in regions:
            ident, offset = region
            result.append((offset, offset + int(self.subregions[ident].size())))

        return result

    def in_subregion(self, bit_offset, bitspan, skip_same=False):
        overlaps = self.get_arg('overlaps')
        
        if overlaps:
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
        overlaps = self.get_arg('overlaps')
        
        if overlaps:
            return 0
        
        offsets = self.subregion_ranges()

        if len(offsets) == 0:
            return 0

        start, end = offsets[-1]
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

        if bit_offset+int(decl.size()) > int(self.size):
            try:
                self.accomodate_subregion(decl, decl.size())
            except Exception as e:
                del self.subregions[id(decl)]
                del self.subregion_offsets[id(decl)]
                raise e

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

        return decl

    def remove_subregion(self, decl):
        if not isinstance(decl, RegionDeclaration):
            raise RegionDeclarationError('decl must be a Declaration object')

        if not self.has_subregion(decl):
            raise RegionDeclarationError('no subregion found')
        
        if not decl.instance is None:
            decl.instance.write_bits([0] * int(decl.size()))

        del self.subregion_offsets[id(decl)]
        del self.subregions[id(decl)]

        if 'parent_declaration' in decl.args:
            del decl.args['parent_declaration']

        if 'address' in decl.args:
            del decl.args['address']

        if 'shift' in decl.args:
            del decl.args['shift']

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
        else:
            data = None
        
        self.remove_subregion(decl)
        self.declare_subregion(decl, new_offset)

        if data:
            decl.instance.write_bits(data)

    def accomodate_subregion(self, decl, new_size):
        if not isinstance(decl, RegionDeclaration):
            raise RegionDeclarationError('decl must be a RegionDeclaration object')

        if not self.has_subregion(decl):
            raise RegionDeclarationError('subregion not found')

        if not isinstance(new_size, Size):
            raise RegionDeclarationError('size must be a Size instance')

        current_offset = self.subregion_offsets[id(decl)]

        if self.in_subregion(current_offset, new_size, True):
            raise RegionDeclarationError('accomodation overwrites another region')

        new_size = current_offset + int(new_size)
        shrink = self.get_arg('shrink')

        if new_size <= int(self.size) and not shrink:
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
        if alignment == Region.ALIGN_BLOCK:
            aligned = align(self.shift + bit_offset, 8)
        else:
            aligned = self.shift + align(bit_offset, alignment)

        return aligned % 8

class RegionError(ParanoiaError):
    pass

class Region(BlockChain):
    DECLARATION_CLASS = None
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
        self.declaration_class = kwargs.setdefault('declaration_class', self.DECLARATION)
        self.declaration = kwargs.setdefault('declaration', self.DECLARATION)

        if self.declaration is None:
            if self.declaration_class is None:
                raise RegionError('both declaration and declaration_class cannot be None')
            
            self.declaration = self.declaration_class(args=kwargs)
        elif is_region(self.declaration):
            self.declaration = self.declaration.declare(**kwargs)

        if not isinstance(self.declaration, Declaration):
            raise RegionError('declaration must be a Declaration object')
        elif not issubclass(self.declaration.base_class, self.__class__):
            raise RegionError('declaration base_class mismatch')

        self.declaration.instance = self

        self.alignment = kwargs.setdefault('alignment', self.ALIGNMENT)
        self.overlaps = kwargs.setdefault('overlaps', self.OVERLAPS)
        self.parent_declaration = kwargs.setdefault('parent_declaration', self.PARENT_DECLARATION)
        self.shrink = kwargs.setdefault('shrink', self.SHRINK)
        self.size = kwargs.setdefault('size', self.SIZE)

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

    def set_address(self, address):
        self.declaration.rebase(address)

    def set_size(self, size):
        self.declaration.set_size(size)

    def parse_bit_data(self, bit_data):
        parsed = self.declaration.bit_parser(bit_data=bit_data
                                             ,shift=self.shift)

        if parsed > self.size:
            self.set_size(parsed)

        self.write_bits(bit_data[:parsed])
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

        self.parse_block_data(block_bytes)

    def set_value(self, value, force=False):
        raise RegionError('set_value not implemented')

    def get_value(self, force=False):
        raise RegionError('get_value not implemented')

    def read_memory(self):
        return map(int, self.block_iterator())

    def __setattr__(self, attr, value):
        if 'declaration' in self.__dict__ and not self.__dict__['declaration'] is None:
            self.__dict__['declaration'].set_arg(attr, value)

        super(Region, self).__setattr__(attr, value)

    @classmethod
    def static_size(cls, **kwargs):
        return cls.SIZE

    @classmethod
    def static_alignment(cls):
        return cls.ALIGNMENT
    
    @classmethod
    def declare(cls, **kwargs):
        declaration_class = kwargs.setdefault('declaration_class', cls.DECLARATION_CLASS)

        if declaration_class is None:
            raise RegionError('declaration class cannot be None')
        
        return declaration_class(base_class=cls, args=kwargs)

    @classmethod
    def bit_parser(cls, **kwargs):
        return cls.static_size(**kwargs)

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
        kwargs = dict()
        kwargs['link_data'] = map(lambda x: x.get_value(force), self.link_iterator())
        dict_merge(kwargs, self.declaration.args)
        
        return self.static_value(**kwargs)

    @classmethod
    def static_value(cls, **kwargs):
        if 'bit_data' in kwargs:
            links = map(lambda x: Block(value=x), bitlist_to_bytelist(kwargs['bit_data']))
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
