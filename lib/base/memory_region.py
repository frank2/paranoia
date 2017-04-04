#!/usr/bin/env python

import ctypes

from paranoia.base import allocator
from paranoia.base import address
from paranoia.base import paranoia_agent
from paranoia.base import declaration
from paranoia.converters import *

try:
    import __builtin__
except ImportError: #python3
    import builtins as __builtin__

__all__ = ['MemoryRegionError', 'sizeof', 'MemoryRegion']

class MemoryRegionError(paranoia_agent.ParanoiaError):
    pass

def sizeof(memory_region):
    if issubclass(memory_region, MemoryRegion):
        return memory_region.static_bytespan()
    elif isinstance(memory_region, MemoryRegion):
        return memory_region.bytespan()
    else:
        raise MemoryRegionError('given argument must be an instance or class deriving MemoryRegion')
    
class MemoryRegion(paranoia_agent.ParanoiaAgent):
    DECLARATION = None
    BITSPAN = None
    MEMORY_BASE = None
    AUTO_ALLOCATE = True
    ALLOCATION = None
    PARENT_REGION = None
    ALLOCATOR_CLASS = allocator.Allocator
    ALLOCATOR = None
    STRING_DATA = None
    INVALIDATED = False
    BITSHIFT = 0
    ALIGNMENT = 8
    ALIGN_BIT = 1
    ALIGN_BYTE = 8

    def __init__(self, **kwargs):
        paranoia_agent.ParanoiaAgent.__init__(self)

        # declaration must come first to properly attribute values
        self.declaration = kwargs.setdefault('declaration', self.DECLARATION)

        if not self.declaration is None and not isinstance(self.declaration, declaration.Declaration):
            raise MemoryRegionError('declaration must implement Declaration')

        if not self.declaration is None and not isinstance(self.declaration.base_class, self):
            raise MemoryRegionError('declaration base_class mismatch')

        if self.declaration is None:
            self.declaration = Declaration(base_class=self.__class__, args=kwargs)
            self.declaration.instance = self

        self.allocator_class = kwargs.setdefault('allocator_class', self.ALLOCATOR_CLASS)
        self.allocator = kwargs.setdefault('allocator', self.ALLOCATOR)
        self.allocation = kwargs.setdefault('allocation', self.ALLOCATION)
        self.alignment = kwargs.setdefault('alignment', self.ALIGNMENT)
        self.auto_allocate = kwargs.setdefault('auto_allocate', self.AUTO_ALLOCATE)
        self.parent_region = kwargs.setdefault('parent_region', self.PARENT_REGION)
        self.bitspan = kwargs.setdefault('bitspan', self.BITSPAN)
        self.memory_base = kwargs.setdefault('memory_base', self.MEMORY_BASE)
        self.invalidated = kwargs.setdefault('invalidated', self.INVALIDATED)
        self.bitshift = kwargs.setdefault('bitshift', self.BITSHIFT)
        self.subregions = dict()
        self.subregion_ids = dict()
        
        string_data = kwargs.setdefault('string_data', self.STRING_DATA)

        if not string_data is None and not isinstance(string_data, str):
            raise MemoryRegionError('string_data must be a string')

        if not self.allocation is None and not isinstance(self.allocation, allocator.Allocation):
            raise MemoryRegionError('allocation must implement allocator.Allocation')

        if self.bitspan is None and not string_data is None:
            self.bitspan = len(string_data)*8

        if not issubclass(self.allocator_class, allocator.Allocator):
            raise MemoryRegionError('allocator class must implement allocator.Allocator')
        if self.alignment is None or self.alignment < 0:
            raise MemoryRegionError('alignment cannot be None or less than 0')

        if self.bitspan is None:
            raise MemoryRegionError('bitspan cannot be None')

        if self.bitshift > 8 or self.bitshift < 0:
            raise MemoryRegionError('bitshift must be within the range of 0-8 noninclusive')

        if not self.parent_region is None and not isinstance(self.parent_region, MemoryRegion):
            raise MemoryRegionError('parent_region must implement MemoryRegion')

        if self.allocator is None:
            self.allocator = self.allocator_class(**kwargs)
        elif not isinstance(self.allocator, allocator.Allocator):
            raise MemoryRegionError('allocator must implement allocator.Allocator')

        if self.memory_base is None:
            if self.auto_allocate:
                self.allocate()
            elif self.allocation:
                self.memory_base = self.allocation.address_object()
            else:
                raise MemoryRegionError('memory_base cannot be None when auto_allocate is False and allocation is None')

        if not self.memory_base is None and not isinstance(self.memory_base, address.Address):
            raise MemoryRegionError('memory_base must be an Address object')

        if not string_data is None:
            self.parse_string_data(string_data)

    def parse_string_data(self, string_data):
        self.write_bytes(list(map(ord, string_data)))

    def subregion_offsets(self):
        keys = self.subregions.keys()
        keys.sort()
        result = list()

        for key in keys:
            result.append((key, key + self.subregions[key].bitspan()))

        return result

    def in_subregion(self, bit_offset, bitspan):
        offsets = self.subregion_offsets()

        for pairing in offsets:
            start, end = pairing

            if bit_offset >= start and bit_offset < end:
                return True

            end_region = bit_offset + bitspan

            if end_region >= start and end_region < end:
                return True

        return False

    def next_subregion_offset(self):
        offsets = self.subregion_offsets()

        if len(offsets) == 0:
            return 0

        start, end = offsets[-1]
        return end

    def has_subregion(self, decl):
        if not isinstance(decl, declaration.Declaration):
            raise MemoryRegionError('decl must be a Declaration object')

        return id(decl) in self.subregion_ids

    def declare_subregion(self, decl, bit_offset=None):
        if not isinstance(decl, declaration.Declaration):
            raise MemoryRegionError('decl must be a Declaration object')

        if not issubclass(decl.base_class, MemoryRegion):
            raise MemoryRegionError('decl base_class must implement MemoryRegion')
        
        if bit_offset is None:
            bit_offset = align(self.next_subregion_offset(), decl.alignment())
        else:
            bit_offset = align(bit_offset, decl.alignment())
            
        aligned_bitspan = align(bit_offset+decl.bitspan(), decl.alignment())
        
        if self.in_subregion(bit_offset, aligned_bitspan):
            raise MemoryRegionError('subregion declaration overwrites another subregion')
        else if aligned_bitspan > self.shifted_bitspan():
            raise MemoryRegionError('subregion exceeds size of parent region')

        decl.args['memory_base'] = self.bit_offset_to_base(bit_offset, decl.alignment())
        decl.args['bitshift'] = self.bit_offset_to_shift(bit_offset, decl.alignment())

        self.subregions[bit_offset] = decl
        self.subregion_ids[id(decl)] = bit_offset

        return bit_offset

    def remove_subregion(self, decl):
        if not isinstance(decl, declaration.Declaration):
            raise MemoryRegionError('decl must be a Declaration object')

        if id(decl) in self.subregion_ids:
            offset = self.subregion_ids[id(decl)]
            del self.subregion_ids[id(decl)]
            del self.subregions[offset]
            return

        raise MemoryRegionError("couldn't find region")

    def move_subregion(self, decl, new_offset):
        if not isinstance(decl, declaration.Declaration):
            raise MemoryRegionError('decl must be a Declaration object')

        if not id(decl) in self.subregion_ids:
            raise MemoryRegionError('subregion not found')

        current_offset = self.subregion_ids[id(decl)]

        if not decl.instance is None:
            data = decl.instance.read_bits()
        else:
            data = None

        self.remove_subregion(decl)
        self.declare_subregion(decl, new_offset)

        if data:
            decl.instance.memory_base = self.bit_offset_to_base(new_offset, decl.alignment())
            decl.instance.bitshift = self.bit_offset_to_shift(new_offset, decl.alignment())
            decl.instance.write_bits(data)

    def resize_subregion(self, decl, new_size):
        if not isinstance(decl, declaration.Declaration):
            raise MemoryRegionError('decl must be a Declaration object')

        if not id(decl) in self.subregion_ids:
            raise MemoryRegionError('subregion not found')

        current_offset = self.subregion_ids[id(decl)]
        
        self.remove_subregion(decl)
        
        old_size = decl.args['bitspan']
        decl.args['bitspan'] = new_size

        try:
            self.declare_subregion(decl, current_offset)
        except Exception, e:
            decl.args['bitspan'] = old_size
            raise e

        if not decl.instance is None:
            decl.instance.bitspan = new_size
        
    def bit_offset_subregion(self, bit_offset):
        if bit_offset in self.subregions:
            return self.subregions[bit_offset]

        keys = self.subregions.keys()
        keys.sort()

        for key in keys:
            key = keys[index]
            subregion = self.subregions[key]

            if bit_offset >= key and bit_offset < key+subregion.bitspan():
                return subregion

        return None

    def bit_offset_to_base(self, bit_offset, alignment):
        aligned = align(bit_offset, alignment)
        bytecount = int(aligned/8) # python3 makes a float

        return self.memory_base.fork(bytecount)

    def bit_offset_to_shift(self, bit_offset, alignment):
        if alignment == MemoryRegion.ALIGN_BIT:
            return bit_offset % 8
        elif alignment == MemoryRegion.ALIGN_BYTE:
            return 0
        else:
            return align(bit_offset, alignment) % 8

    def bytespan(self):
        aligned = align(self.bitspan, self.alignment)
        bytecount = int(aligned/8)
        extra = int(aligned % 8 != 0)
        
        return bytecount + extra

    def shifted_bitspan(self):
        return self.bitspan + self.bitshift

    def shifted_bytespan(self):
        aligned = align(self.shifted_bitspan(), self.alignment)
        bytecount = int(aligned/8) # python3 turns this into a float
        extra = int(aligned % 8 != 0)
        
        return bytecount + extra

    def read_bytestring(self, byte_length, byte_offset=0):
        if self.invalidated:
            raise MemoryRegionError('memory region has been invalidated')
        
        if (byte_length+byte_offset)*8 > align(self.bitspan+self.bitshift, 8): 
            raise MemoryRegionError('byte length and offset exceed aligned bitspan (%d, %d, %d)' % (byte_length, byte_offset, align(self.bitspan+self.bitshift, 8)))

        if self.allocation:
            return self.allocation.read_bytestring(byte_length, byte_offset)
        else:
            string_at = ctypes.string_at(int(self.memory_base)+byte_offset, byte_length)

            if isinstance(string_at, str): # python 2
                string_at = bytearray(string_at)

            return string_at

    def read_string(self, byte_length, byte_offset=0, encoding='ascii'):
        self.read_bytestring(byte_length, byte_offset).decode(encoding)
    
    def read_bytes(self, byte_length, byte_offset=0):
        return list(self.read_bytestring(byte_length, byte_offset))

    def read_bytelist_for_bits(self, bit_length, bit_offset=0, hinting=True):
        if bit_length + bit_offset > self.bitspan:
            raise MemoryRegionError('bit length and offset exceed bitspan')

        # true_offset represents where in the first byte to start reading bits
        if hinting:
            true_offset = self.bitshift + bit_offset
        else:
            true_offset = bit_offset

        # get the number of bytes necessary to grab our contextual bits
        byte_length = int(align(bit_length+(true_offset % 8), 8)/8)

        # convert the bytes into a string of bits
        return self.read_bytes(byte_length, int(true_offset/8))

    def read_bitlist_from_bytes(self, bit_length, bit_offset=0, hinting=True):
        if bit_length + bit_offset > self.bitspan:
            raise MemoryRegionError('bit length and offset exceed bitspan')

        unconverted_bytes = self.read_bytelist_for_bits(bit_length, bit_offset, hinting)
        
        return ''.join(map('{0:08b}'.format, unconverted_bytes))

    def read_bits_from_bytes(self, bit_length, bit_offset=0, hinting=True):
        # take only the contextual bits based on the bit_length
        if bit_length + bit_offset > self.bitspan:
            raise MemoryRegionError('bit length and offset exceed bitspan')

        # true_offset represents where in the first byte to start reading bits

        if hinting:
            true_offset = self.bitshift + (bit_offset % 8)
            start_index = self.bitshift
        else:
            true_offset = bit_offset % 8

        converted_bytes = self.read_bitlist_from_bytes(bit_length, bit_offset)

        return list(map(int, converted_bytes))[true_offset:bit_length+true_offset]

    def read_bits(self, bit_length=None, bit_offset=0, hinting=True):
        if not bit_length:
            bit_length = self.bitspan

        return self.read_bits_from_bytes(bit_length, bit_offset, hinting)

    def read_bytes_from_bits(self, bit_length, bit_offset=0, hinting=True):
        return bitlist_to_bytelist(self.read_bits_from_bytes(bit_length, bit_offset, hinting))

    def read_memory(self):
        return self.read_bytestring(self.shifted_bytespan())
    
    def write_bytestring(self, string_val, byte_offset=0):
        if self.invalidated:
            raise MemoryRegionError('memory region has been invalidated')
        
        if (len(string_val)+byte_offset)*8 > align(self.bitspan+self.bitshift, 8):
            raise MemoryRegionError('list plus offset exceeds memory region boundary')

        if self.allocation:
            self.allocation.write_bytestring(string_val, byte_offset)
        else:
            string_buffer = ctypes.create_string_buffer(bytes(string_val))
            string_address = ctypes.addressof(string_buffer)
            ctypes.memmove(int(self.memory_base)+byte_offset, string_address, len(string_val))

    def write_bytes(self, byte_list, byte_offset=0):
        return self.write_bytestring(bytearray(byte_list), byte_offset)

    def write_bits(self, bit_list, bit_offset=0, hinting=True):
        if len(bit_list) + bit_offset > self.bitspan:
            raise MemoryRegionError('list plus offset exceeds memory region boundary')

        if hinting:
            true_offset = self.bitshift + bit_offset
        else:
            true_offset = bit_offset
            
        true_terminus = true_offset + len(bit_list)
        byte_start = int(true_offset/8)
        byte_end = int(true_terminus/8)

        # value represents the number of bits which overwrite the underlying byte
        if byte_start == byte_end:
            single_shift = ((8 - len(bit_list)) - true_offset % 8)
            value_mask = ((2 ** len(bit_list)) - 1) << single_shift
            underlying_mask = 0xFF ^ value_mask
            underlying_value = self.read_bytes(1, byte_start)[0]
            bit_value = bitlist_to_numeric(bit_list) << single_shift
            mask_result = underlying_value & underlying_mask | bit_value

            self.write_bytes([mask_result], byte_start)
            return

        front_remainder = alignment_delta(true_offset, 8)

        if front_remainder:
            front_bits = bit_list[:front_remainder]
            front_byte_mask = (0xFF ^ (2 ** front_remainder) - 1)
            front_byte_value = self.read_bytes(1, byte_start)[0]
            front_bit_value = bitlist_to_numeric(front_bits)
            mask_result = front_byte_value & front_byte_mask | front_bit_value

            self.write_bytes([mask_result], byte_start)            
            byte_start += 1

        # value represents the number of bits which overwrite the underlying byte
        back_remainder = true_terminus % 8

        if back_remainder:
            back_bits = bit_list[len(bit_list) - back_remainder:]
            back_byte_mask = (2 ** back_remainder) - 1
            back_byte_value = self.read_bytes(1, byte_end)[0]
            back_bit_value = bitlist_to_numeric(back_bits)
            mask_result = back_byte_value & back_byte_mask | (back_bit_value << (8 - back_remainder))
            
            self.write_bytes([mask_result], byte_end)

        bytebound_list = bit_list[front_remainder:(len(bit_list) - back_remainder)]
        bytebound_list = bitlist_to_bytelist(bytebound_list)
        self.write_bytes(bytebound_list, byte_start)

    def write_bits_from_bytes(self, byte_list, bit_offset=0, hinting=True):
        self.write_bits(bytelist_to_bitlist(byte_list), bit_offset, hinting)

    def write_bytes_from_bits(self, bit_list, byte_offset=0):
        self.write_bytes(bitlist_to_bytelist(bit_list), byte_offset)

    def move_bits(self, offset_dest, offset_source, length):
        bitlist = self.read_bits(length, offset_source, False)
        self.write_bits([0] * length, offset_source, False)
        self.write_bits(bitlist, offset_dest, False)

    def move_bytes(self, offset_dest, offset_source, length):
        bytelist = self.read_bytes(length, offset_source)
        self.write_bytes([0] * len(bytelist), offset_source)
        self.write_bytes(bytelist, offset_dest)

    def root_parent(self):
        root_parent = self

        while not root_parent.parent_region == None:
            root_parent = root_parent.parent_region

        return root_parent

    def is_allocated(self):
        return not self.allocation is None

    def allocate(self):
        self.allocation = self.allocator.allocate(self.shifted_bytespan())
        self.memory_base = self.allocation.address_object()

    def reallocate(self):
        if not self.parent_region is None:
            return self.parent_region.reallocate(new_bitspan)
        
        if not self.is_allocated():
            return

        shifted_bytespan = self.shifted_bytespan()
        
        if self.allocation.size == shifted_bytespan:
            return
        
        self.allocation.reallocate(self.shifted_bytespan())

    def __hash__(self):
        return hash('%X/%d/%d' % (int(self.memory_base), self.bitspan, self.bitshift))

    def __setattr__(self, attr, value):
        if 'declaration' in self.__dict__ and not self.__dict__['declaration'] is None:
            self.__dict__['declaration'].set_arg(attr, value)

        paranoia_agent.ParanoiaAgent.__setattr__(self, attr, value)

    @classmethod
    def static_bitspan(cls, **kwargs):
        return kwargs.setdefault('bitspan', cls.BITSPAN)

    @classmethod
    def static_alignment(cls):
        return cls.ALIGNMENT

    @classmethod
    def static_bytespan(cls, **kwargs):
        bitspan = cls.static_bitspan(**kwargs)
        alignment = cls.static_alignment()
        return int(align(bitspan, alignment) / 8)

    @classmethod
    def static_declaration(cls, **kwargs):
        kwargs.setdefault('auto_allocate', cls.AUTO_ALLOCATE)
        kwargs.setdefault('parent_region', cls.PARENT_REGION)
        kwargs.setdefault('allocator_class', cls.ALLOCATOR_CLASS)
        kwargs.setdefault('allocator', cls.ALLOCATOR)
        kwargs.setdefault('bitspan', cls.BITSPAN)
        kwargs.setdefault('memory_base', cls.MEMORY_BASE)
        kwargs.setdefault('bitshift', cls.BITSHIFT)

        class StaticMemoryRegion(cls):
            AUTO_ALLOCATE = kwargs['auto_allocate']
            PARENT_REGION = kwargs['parent_region']
            ALLOCATOR_CLASS = kwargs['allocator_class']
            ALLOCATOR = kwargs['allocator']
            BITSPAN = kwargs['bitspan']
            MEMORY_BASE = kwargs['memory_base']
            BITSHIFT = kwargs['bitshift']

        return StaticMemoryRegion
