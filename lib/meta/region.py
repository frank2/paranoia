#!/usr/bin/env python

import ctypes
import inspect
import sys

from paranoia.base.allocator import heap, Allocator
from paranoia.base.block import BlockChain
from paranoia.base.paranoia_agent import ParanoiaAgent, ParanoiaError
from paranoia.base import parser
from paranoia.meta.declaration import Declaration
from paranoia.fundamentals import *

try:
    import __builtin__
except ImportError: #python3
    import builtins as __builtin__

__all__ = ['MemoryRegionError', 'sizeof', 'MemoryRegion']

class MemoryRegionError(ParanoiaError):
    pass

class NewRegion(BlockChain):
    DECLARATION = None
    PARENT_REGION = None
    VALUE = None
    BIND = False
    OVERLAPS = False
    STATIC = False
    SHRINK = False
    ALIGN_BIT = 1
    ALIGN_BYTE = 8
    ALIGNMENT = 8

    def __init__(self, **kwargs):
        super(NewRegion, self).__init__(**kwargs)
        
        self.alignment = kwargs.setdefault('alignment', self.ALIGNMENT)
        
def sizeof(memory_region):
    if issubclass(memory_region, MemoryRegion):
        return memory_region.static_bytespan()
    elif isinstance(memory_region, MemoryRegion):
        return memory_region.bytespan()
    else:
        raise MemoryRegionError('given argument must be an instance or class deriving MemoryRegion')

def is_region_class(obj):
    return inspect.isclass(obj) and issubclass(obj, MemoryRegion)

def ensure_declaration(obj):
    if isinstance(obj, declaration.Declaration):
        return obj
    elif is_region_class(obj):
        return obj.declare()
    else:
        raise MemoryRegionError('declaration must be either a Declaration object or a MemoryRegion class')

class MemoryRegionParser(parser.Parser):
    def __init__(self, decl):
        parser.Parser.__init__(self, decl)
        self.bits_consumed = 0
        
    def consume(self):
        decl = self.declaration
        consumed = super(MemoryRegionParser, self).consume()

        if not decl.instance is None:
            decl.instance.write_bits(consumed, self.bits_consumed)
            
        self.bits_consumed += len(consumed)

        return consumed

    def feed(self, data=None):
        if not self.state == parser.Parser.STATE_FEED:
            raise parser.ParserError('parser not ready for feeding')

        if data is None:
            if len(self.tape):
                data = self.tape
            elif self.declaration.get_arg('parse_memory'):
                data = self.read_bits(self.last_state.want, self.bits_consumed)
            else:
                raise ParseError('unexpected end of file')

        self.gen_obj.send(data)
        self.state = parser.Parser.STATE_CONSUME
        
    def generate(self):
        decl = self.declaration
        data = decl.get_arg('data')
        bitshift = decl.get_arg('bitshift')
        bitspan = decl.bitspan()

        tape = bytelist_to_bitlist(map(ord, data))

        if bitshift > 0:
            tape = tape[bitshift:]

        yield tape

        consumed = tape[:bitspan]
        total_read = len(consumed)
        bitspan -= total_read
        unconsumed = tape[total_read:]

        while bitspan > 0:
            yield parser.ParserState(unconsumed, total_read, bitspan)
            tape = yield
                
            consumed = tape[:bitspan]
            total_read = len(consumed)
            bitspan -= total_read
            unconsumed = tape[total_read:]

        yield parser.ParserState(unconsumed, total_read, 0)
    
class MemoryRegion(paranoia_agent.ParanoiaAgent):
    DECLARATION = None
    BITSPAN = None
    MEMORY_BASE = None
    AUTO_ALLOCATE = True
    ALLOCATION = None
    PARENT_REGION = None
    ALLOCATOR_CLASS = allocator.Allocator
    ALLOCATOR = allocator.heap
    PARSER_CLASS = MemoryRegionParser
    DATA = None
    VALUE = None
    ZERO_MEMORY = False
    BIND = False
    OVERLAPS = False
    PARSE_MEMORY = False
    STATIC = False
    SHRINK = False
    MAXIMUM_SIZE = 0
    BITSHIFT = 0
    ALIGNMENT = 8
    ALIGN_BIT = 1
    ALIGN_BYTE = 8

    def __init__(self, **kwargs):
        paranoia_agent.ParanoiaAgent.__init__(self)

        # declaration must come first to properly attribute values
        self.declaration = kwargs.setdefault('declaration', self.DECLARATION)

        if not self.declaration is None:
            self.declaration = ensure_declaration(self.declaration)
        else:
            self.declaration = declaration.Declaration(base_class=self.__class__, args=kwargs)
            
        self.declaration.instance = self

        kwargs['declaration'] = self.declaration

        if not issubclass(self.declaration.base_class, self.__class__):
            raise MemoryRegionError('declaration base_class mismatch')

        self.allocator_class = kwargs.setdefault('allocator_class', self.ALLOCATOR_CLASS)
        self.allocator = kwargs.setdefault('allocator', self.ALLOCATOR)
        self.allocation = kwargs.setdefault('allocation', self.ALLOCATION)
        self.parser_class = kwargs.setdefault('parser_class', self.PARSER_CLASS)
        self.alignment = kwargs.setdefault('alignment', self.ALIGNMENT)
        self.auto_allocate = kwargs.setdefault('auto_allocate', self.AUTO_ALLOCATE)
        self.parent_region = kwargs.setdefault('parent_region', self.PARENT_REGION)
        self.bitspan = kwargs.setdefault('bitspan', self.BITSPAN)
        self.bitshift = kwargs.setdefault('bitshift', self.BITSHIFT)
        self.memory_base = kwargs.setdefault('memory_base', self.MEMORY_BASE)
        self.zero_memory = kwargs.setdefault('zero_memory', self.ZERO_MEMORY)
        self.bind = kwargs.setdefault('bind', self.BIND)
        self.overlaps = kwargs.setdefault('overlaps', self.OVERLAPS)
        self.maximum_size = kwargs.setdefault('maximum_size', self.MAXIMUM_SIZE)
        self.shrink = kwargs.setdefault('shrink', self.SHRINK)
        self.static = False # change this at the end of the constructor
        self.subregions = dict()
        self.subregion_offsets = dict()
        self.init_finished = False
        
        data = kwargs.setdefault('data', self.DATA)
        value = kwargs.setdefault('value', self.VALUE)
        parse_memory = kwargs.setdefault('parse_memory', self.PARSE_MEMORY)
        parser = None

        if not data is None and not isinstance(data, str):
            raise MemoryRegionError('data must be a string')

        if not self.allocation is None and not isinstance(self.allocation, allocator.Allocation):
            raise MemoryRegionError('allocation must implement allocator.Allocation')

        if not issubclass(self.allocator_class, allocator.Allocator):
            raise MemoryRegionError('allocator class must implement allocator.Allocator')
        if self.alignment is None or self.alignment < 0:
            raise MemoryRegionError('alignment cannot be None or less than 0')

        if self.bitspan is None:
            raise MemoryRegionError('bitspan cannot be None')

        if self.bitshift > 8 or self.bitshift < 0:
            raise MemoryRegionError('bitshift must be within the range of 0 <= x < 8')

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

        if not self.memory_base is None and not isinstance(self.memory_base, allocator.Address):
            raise MemoryRegionError('memory_base must be an Address object')

        if not parse_memory and self.zero_memory and not self.bitspan == 0:
            self.write_bits([0] * self.bitspan)

        if parse_memory or not data is None:
            parser = self.declaration.parser()
        elif not value is None:
            self.set_value(value)

        if not parser is None:
            parser.run()

        self.static = kwargs.setdefault('static', self.STATIC)
        self.init_finished = True

    def is_bound(self):
        return self.bind and self.init_finished

    def rebase(self, new_base, new_shift):
        if not isinstance(new_base, address.Address):
            raise MemoryRegionError('new memory base must be an Address object')

        self.memory_base = new_base
        self.bitshift = new_shift

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
                decl.set_arg('memory_base', new_sub_base)
                decl.set_arg('bitshift', new_sub_shift)

    def subregion_ranges(self):
        regions = self.subregion_offsets.items()
        regions.sort(lambda x,y: cmp(x[1], y[1]))
        result = list()

        for region in regions:
            ident, offset = region
            result.append((offset, offset + self.subregions[ident].bitspan()))

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
        if not isinstance(decl, declaration.Declaration):
            raise MemoryRegionError('decl must be a Declaration object')

        return id(decl) in self.subregions

    def declare_subregion(self, decl, bit_offset=None):
        if not isinstance(decl, declaration.Declaration):
            raise MemoryRegionError('decl must be a Declaration object')

        if self.has_subregion(decl):
            raise MemoryRegionError('region already has subregion declaration')
        
        if bit_offset is None:
            bit_offset = align(self.next_subregion_offset(), decl.alignment())
        else:
            bit_offset = align(bit_offset, decl.alignment())
        
        if self.in_subregion(bit_offset, decl.bitspan()):
             raise MemoryRegionError('subregion declaration overwrites another subregion')

        self.subregions[id(decl)] = decl
        self.subregion_offsets[id(decl)] = bit_offset

        if bit_offset+decl.bitspan() > self.shifted_bitspan():
            try:
                self.accomodate_subregion(decl, decl.bitspan())
            except Exception as e:
                del self.subregions[id(decl)]
                del self.subregion_offsets[id(decl)]
                raise e

        new_base = self.bit_offset_to_base(bit_offset, decl.alignment())
        new_shift = self.bit_offset_to_shift(bit_offset, decl.alignment())

        if not decl.instance is None:
            decl.instance.rebase(new_base, new_shift)
        else:
            decl.set_arg('memory_base', new_base)
            decl.set_arg('bitshift', new_shift)

        return decl

    def remove_subregion(self, decl):
        if not isinstance(decl, declaration.Declaration):
            raise MemoryRegionError('decl must be a Declaration object')

        if not self.has_subregion(decl):
            raise MemoryRegionError('no subregion found')
        
        if not decl.instance is None and decl.instance.zero_memory:
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
            raise MemoryRegionError('decl must be a Declaration object')

        if not self.has_subregion(decl):
            raise MemoryRegionError('subregion not found')

        current_offset = self.subregion_offsets[id(decl)]

        if self.in_subregion(current_offset, new_size, True):
            raise MemoryRegionError('accomodation overwrites another region')

        new_size = current_offset + new_size

        if new_size <= self.bitspan and not self.shrink:
            return

        self.resize(new_size)

    def resize_subregion(self, decl, new_size):
        if not isinstance(decl, declaration.Declaration):
            raise MemoryRegionError('decl must be a Declaration object')

        if not self.has_subregion(decl):
            raise MemoryRegionError('subregion not found')
        
        self.accomodate_subregion(decl, new_size)

        current_offset = self.subregion_offsets[id(decl)]

        self.remove_subregion(decl)

        old_size = decl.get_arg('bitspan')
        decl.set_arg('bitspan', new_size)

        try:
            self.declare_subregion(decl, current_offset)
        except Exception as e:
            decl.set_arg('bitspan', old_size)
            raise e

        if not decl.instance is None:
            decl.instance.bitspan = new_size
        
    def bit_offset_subregions(self, bit_offset):
        current_offsets = self.subregion_offsets.items()
        current_offsets = filter(lambda x: x == bit_offset, current_offsets)
        
        if len(current_offsets):
            return map(lambda x: self.subregions[x], current_offsets)

        results = list()
        
        for ident in self.subregions:
            subregion = self.subregions[ident]
            ident_offset = self.subregion_offsets[ident]

            if bit_offset >= ident_offset and bit_offset < ident_offset+subregion.bitspan():
                results.append(ident)

        if len(results):
            return map(lambda x: self.subregions[x], results)

    def bit_offset_to_base(self, bit_offset, alignment):
        aligned = align(self.bitshift + bit_offset, alignment)
        bytecount = int(aligned/8) # python3 makes a float

        return self.memory_base.fork(bytecount)

    def bit_offset_to_shift(self, bit_offset, alignment):
        fixed_offset = self.bitshift + bit_offset
        
        if alignment == MemoryRegion.ALIGN_BIT:
            return fixed_offset % 8
        elif alignment == MemoryRegion.ALIGN_BYTE:
            return 0
        else:
            return align(fixed_offset, alignment) % 8

    def bytespan(self):
        aligned = align(self.bitshift+self.bitspan, self.alignment)
        bytecount = int(aligned/8)
        extra = int(not aligned % 8 == 0)
        
        return bytecount + extra

    def shifted_bitspan(self):
        return self.bitspan + self.bitshift

    def shifted_bytespan(self):
        aligned = align(self.shifted_bitspan(), self.alignment)
        bytecount = int(aligned/8) # python3 turns this into a float
        extra = int(aligned % 8 != 0)
        
        return bytecount + extra

    def read_bytestring(self, byte_length, byte_offset=0):
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
        if self.static:
            raise MemoryRegionError('cannot write to a static region')
        
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

    def reallocate(self, new_allocation=None):
        if not self.is_allocated():
            raise MemoryRegionError('region was not allocated')

        if self.is_bound():
            raise MemoryRegionError('cannot reallocate a bound memory region')
        
        if new_allocation is None:
            shifted_bytespan = self.shifted_bytespan()
        else:
            shifted_bytespan = int(new_allocation / 8)
            shifted_bytespan += int(not new_allocation % 8 == 0)

        maximum_bytespan = (self.maximum_size)/8 + int(not self.maximum_size % 8 == 0)
        
        if not self.maximum_size == 0 and shifted_bytespan > maximum_bytespan:
            raise MemoryRegionError('new size exceeds maximum size')

        if self.allocation.size == shifted_bytespan:
            return

        self.allocation.reallocate(shifted_bytespan)

    def resize(self, new_bitspan):
        if not self.maximum_size == 0 and new_bitspan > self.maximum_size:
            raise MemoryRegionError('new size exceeds maximum size')
        
        if not self.parent_region is None: # subregion
            self.parent_region.resize_subregion(self.declaration, new_bitspan)
            return

        self.reallocate(new_bitspan)
        self.bitspan = new_bitspan

    def hexdump(self):
        bytelist = self.read_memory()
        bitlist = self.read_bits()
        bit_delta = -self.bitshift
        byte_iterator = 0
        bit_iterator = 0

        while byte_iterator < align(len(bytelist), 8):
            if byte_iterator % 8 == 0:
                sys.stdout.write('%08X:%04X:X ' % (int(self.memory_base)+byte_iterator, byte_iterator))

            if byte_iterator < len(bytelist):
                sys.stdout.write('%02X%6s ' % (bytelist[byte_iterator], ''))
            else:
                sys.stdout.write('%8s ' % '')

            if byte_iterator % 8 == 7:
                for i in xrange(8):
                    if byte_iterator-7+i >= len(bytelist):
                        break
                    
                    byte_val = bytelist[byte_iterator-7+i]

                    if byte_val >= 32 and byte_val <= 127:
                        sys.stdout.write(chr(byte_val))
                    else:
                        sys.stdout.write('.')
                        
                sys.stdout.write('\n')
                sys.stdout.write('%08X:%04X:B ' % (int(self.memory_base)+(byte_iterator-7), byte_iterator-7))
                
                while bit_iterator + bit_delta < len(bitlist):
                    bit_offset = bit_iterator + bit_delta
                    
                    if bit_offset < 0 or bit_offset >= self.bitspan:
                        sys.stdout.write(' ')
                    else:
                        sys.stdout.write('%d' % bitlist[bit_offset])

                    if bit_iterator % 8 == 7:
                        sys.stdout.write(' ')

                    bit_iterator += 1

                    if bit_iterator % 64 == 0:
                        break

                sys.stdout.write('\n\n')
                
            byte_iterator += 1

    def set_value(self, value):
        raise MemoryRegionError('MemoryRegion does not implement set_value')

    def get_value(self, value):
        raise MemoryRegionError('MemoryRegion does not implement get_value')

    def __hash__(self):
        return hash('%X/%d/%d' % (int(self.memory_base), self.bitspan, self.bitshift))

    def __setattr__(self, attr, value):
        if 'declaration' in self.__dict__ and not self.__dict__['declaration'] is None:
            self.__dict__['declaration'].set_arg(attr, value)

        paranoia_agent.ParanoiaAgent.__setattr__(self, attr, value)

    @classmethod
    def static_value(cls, **kwargs):
        raise MemoryRegionError('MemoryRegion does not implement static_value')
    
    @classmethod
    def declare(cls, **kwargs):
        return declaration.Declaration(base_class=cls, args=kwargs)

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
    def subclass(cls, **kwargs):
        kwargs.setdefault('allocator_class', cls.ALLOCATOR_CLASS)
        kwargs.setdefault('allocator', cls.ALLOCATOR)
        kwargs.setdefault('allocation', cls.ALLOCATION)
        kwargs.setdefault('alignment', cls.ALIGNMENT)
        kwargs.setdefault('auto_allocate', cls.AUTO_ALLOCATE)
        kwargs.setdefault('parent_region', cls.PARENT_REGION)
        kwargs.setdefault('bitspan', cls.BITSPAN)
        kwargs.setdefault('bitshift', cls.BITSHIFT)
        kwargs.setdefault('memory_base', cls.MEMORY_BASE)
        kwargs.setdefault('zero_memory', cls.ZERO_MEMORY)
        kwargs.setdefault('bind', cls.BIND)
        kwargs.setdefault('overlaps', cls.OVERLAPS)
        kwargs.setdefault('shrink', cls.SHRINK)
        kwargs.setdefault('maximum_size', cls.MAXIMUM_SIZE)
        kwargs.setdefault('data', cls.DATA)
        kwargs.setdefault('value', cls.VALUE)
        kwargs.setdefault('parse_memory', cls.PARSE_MEMORY)

        class SubclassedMemoryRegion(cls):
            ALLOCATOR_CLASS = kwargs['allocator_class']
            ALLOCATOR = kwargs['allocator']
            ALLOCATION = kwargs['allocation']
            ALIGNMENT = kwargs['alignment']
            AUTO_ALLOCATE = kwargs['auto_allocate']
            PARENT_REGION = kwargs['parent_region']
            BITSPAN = kwargs['bitspan']
            BITSHIFT = kwargs['bitshift']
            MEMORY_BASE = kwargs['memory_base']
            ZERO_MEMORY = kwargs['zero_memory']
            BIND = kwargs['bind']
            OVERLAPS = kwargs['overlaps']
            SHRINK = kwargs['shrink']
            MAXIMUM_SIZE = kwargs['maximum_size']
            DATA = kwargs['data']
            VALUE = kwargs['value']
            PARSE_MEMORY = kwargs['parse_memory']

        return SubclassedMemoryRegion
