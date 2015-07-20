#!/usr/bin/env python

import ctypes
import os
import sys

# the goal is to implement the primitives of C. they are:
#
# * bitfield
# * byte
# * word
# * dword
# * qword
# * char
# * wchar
# * array
# * structure
# * union
# * enum
#
# * a bitfield is an arbitrary series of bits
# * a byte is an 8-bit bitfield
# * a word is a 16-bit bitfield
# * a dword is a 32-bit bitfield
# * a qword is a 64-bit bitfield
# * a char is a byte
# * a wchar is a word
# * a structure is an arbitrary series of primitives
# * a union is a structure whose variables all take up the same bit offset
#
# the kicker is that memory regions are in terms of bytes. this means that the
# region underlying all this data needs to be byte-aware but also expose bit-level
# functionality.

def aligned(base, alignment):
    return base % alignment == 0

def alignment_delta(base, alignment):
    return (alignment - (base % alignment)) * int(not aligned(base, alignment))

def align(base, alignment):
    return base + alignment_delta(base, alignment)

def bitlist_to_bytelist(bitlist):
    bitlist = bitlist[::-1]
    bytelist = list()
    byte_value = 0
    
    for i in xrange(len(bitlist)):
        if i % 8 == 0 and not i == 0:
            byte_value = 0

        byte_value |= bitlist[i] << (i % 8)

        # this is the last bit for the byte
        if (i+1) % 8 == 0:
            bytelist.append(byte_value)

    # that's all for the bits, add the last byte value found
    if not len(bitlist) % 8 == 0:
        bytelist.append(byte_value)

    # reverse the bytelist to match the original direction of the bits
    return bytelist[::-1]

def bytelist_to_bitlist(bytelist):
    return map(int, ''.join(map('{0:08b}'.format, bytelist)))

def bitlist_to_numeric(bitlist):
    bitlist = bitlist[::-1]

    byte_value = 0

    for i in xrange(len(bitlist)):
        byte_value |= bitlist[i] << i

    return byte_value

def numeric_to_bitlist(numeric):
    bitlist = list()

    while numeric > 0:
        bitlist.append(numeric & 1)
        numeric >>= 1

    return bitlist[::-1]

class ParanoiaAgent(object):
    pass

class ParanoiaError(Exception):
    pass

class AllocatorError(ParanoiaError):
    pass

class Allocator(ParanoiaAgent):
    def __init__(self, **kwargs):
        self.address_map = dict()

    def allocate(self, byte_length):
        if not isinstance(byte_length, (int, long)):
            raise AllocatorError('integer value not given')

        c_string = ctypes.create_string_buffer(byte_length)
        c_address = ctypes.addressof(c_string)
        self.address_map[c_address] = c_string

        return c_address

    def allocate_string(self, string):
        if not isinstance(string, basestring):
            raise AllocatorError('string value not given')

        c_string = ctypes.create_string_buffer(string)
        c_address = ctypes.addressof(c_string)
        self.address_map[c_address] = c_string
        
        return c_address

    def deallocate(self, address):
        if not self.address_map.has_key(address):
            raise AllocatorError('no such address allocated: 0x%x' % address)

        c_string = self.address_map[address]

        del c_string
        del self.address_map[address]

class MemoryRegionError(ParanoiaError):
    pass

class MemoryRegion(ParanoiaAgent):
    BITSPAN = None
    MEMORY_BASE = None
    BITSHIFT = 0
    VIRTUAL_BASE = 0

    def __init__(self, **kwargs):
        self.bitspan = kwargs.setdefault('bitspan', self.BITSPAN)
        self.memory_base = kwargs.setdefault('memory_base', self.MEMORY_BASE)
        self.bitshift = kwargs.setdefault('bitshift', self.BITSHIFT)
        self.virtual_base = kwargs.setdefault('virtual_base', self.VIRTUAL_BASE)

        if self.bitspan is None or self.bitspan == 0:
            raise MemoryRegionError('bitspan cannot be None or 0')

        if self.memory_base is None:
            raise MemoryRegionError('memory_base cannot be None')

        if self.bitshift > 8 or self.bitshift < 0:
            raise MemoryRegionError('bitshift must be within the range of 0-8 noninclusive')

    def read_bytes(self, byte_length, byte_offset=0):
        if (byte_length+byte_offset)*8 > align(self.bitspan, 8): 
            raise MemoryRegionError('byte length and offset exceed aligned bitspan')

        try:
            return map(ord, ctypes.string_at(self.memory_base+byte_offset, byte_length))
        except:
            raise MemoryRegionError('raw memory access failed')

    def read_bits_from_bytes(self, bit_length, bit_offset=0):
        # true_offset represents where in the first byte to start reading bits
        true_offset = self.bitshift + bit_offset

        if bit_length + bit_offset > self.bitspan:
            raise MemoryRegionError('bit length and offset exceed bitspan')

        # get the number of bytes necessary to grab our contextual bits
        byte_length = align(bit_length+(true_offset % 8), 8)/8

        # convert the bytes into a string of bits
        converted_bytes = ''.join(map('{0:08b}'.format, self.read_bytes(byte_length, true_offset/8)))

        # take only the contextual bits based on the bit_length
        return map(int, converted_bytes)[true_offset % 8:bit_length + (true_offset % 8)]

    def read_bytes_from_bits(self, bit_length, bit_offset=0):
        return bitlist_to_bytelist(self.read_bits_from_bytes(bit_length, bit_offset))

    def write_bytes(self, byte_list, byte_offset=0):
        if (len(byte_list)+byte_offset)*8 > align(self.bitspan, 8):
            raise MemoryRegionError('list plus offset exceeds memory region boundary')

        string_buffer = ctypes.create_string_buffer(''.join(map(chr, byte_list)))

        try:
            ctypes.memmove(self.memory_base+byte_offset, ctypes.addressof(string_buffer), len(byte_list))
        except:
            raise MemoryRegionError('write exceeds region boundaries')

    def write_bits(self, bit_list, bit_offset=0):
        if len(bit_list) + bit_offset > self.bitspan:
            raise MemoryRegionErropr('list plus offset exceeds memory region boundary')

        true_offset = self.bitshift + bit_offset
        true_terminus = true_offset + len(bit_list)
        byte_start = true_offset/8
        byte_end = true_terminus/8

        # value represents the number of bits which overwrite the underlying byte
        front_remainder = alignment_delta(true_offset, 8)

        if front_remainder:
            front_bits = bit_list[:front_remainder]
            front_byte_mask = (0xFF ^ (2 ** front_remainder) - 1)
            front_byte_value = self.read_bytes(1, byte_end)[0]
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

    def write_bits_from_bytes(self, byte_list, bit_offset=0):
        self.write_bits(bytelist_to_bitlist(byte_list), bit_offset)

    def write_bytes_from_bits(self, bit_list, byte_offset=0):
        self.write_bytes(bitlist_to_bytelist(bit_list), byte_offset)

    def __hash__(self):
        return hash('%X/%d/%d' % (self.memory_base, self.bitspan, self.bitshift))

    @classmethod
    def static_bitspan(cls):
        return cls.BITSPAN

    @classmethod
    def static_declaration(cls, **kwargs):
        kwargs.setdefault('bitspan', cls.BITSPAN)
        kwargs.setdefault('memory_base', cls.MEMORY_BASE)
        kwargs.setdefault('bitshift', cls.BITSHIFT)
        kwargs.setdefault('virtual_base', cls.VIRTUAL_BASE)

        class StaticMemoryRegion(cls):
            BITSPAN = kwargs['bitspan']
            MEMORY_BASE = kwargs['memory_base']
            BITSHIFT = kwargs['bitshift']
            VIRTUAL_BASE = kwargs['virtual_base']

        return StaticMemoryRegion

class NumericRegionError(MemoryRegionError):
    pass

class NumericRegion(MemoryRegion):
    LITTLE_ENDIAN = 0
    BIG_ENDIAN = 1
    ENDIANNESS = 0
    UNSIGNED = 0
    SIGNED = 1
    SIGNAGE = 0
    VALUE = None

    def __init__(self, **kwargs):
        self.endianness = kwargs.setdefault('endianness', self.ENDIANNESS)

        if not self.endianness == self.LITTLE_ENDIAN and not self.endianness == self.BIG_ENDIAN:
            raise NumericRegionError('endianness must be NumericRegion.LITTLE_ENDIAN or NumericRegion.BIG_ENDIAN')

        self.signage = kwargs.setdefault('signage', self.SIGNAGE)

        if not self.signage == self.SIGNED and not self.signage == self.UNSIGNED:
            raise NumericRegionError('signage must be NumericRegion.SIGNED or NumericRegion.UNSIGNED')

        MemoryRegion.__init__(self, **kwargs)

        value = kwargs.setdefault('value', self.VALUE)

        if not value is None:
            self.set_value(value)

    def get_value(self):
        bitlist = self.read_bits_from_bytes(self.bitspan)
        bitspan_content = bitlist_to_bytelist(bitlist)

        # the bytelist comes out endian-agnostic, so if it's little endian, we
        # need to reverse it.
        if self.endianness == NumericRegion.LITTLE_ENDIAN:
            bitspan_content = bitspan_content[::-1]

        value = 0

        for i in xrange(len(bitspan_content)):
            value <<= 8
            value |= bitspan_content[i]

        return value

    def set_value(self, value):
        bytelist = list()
        bitspan = self.bitspan
        old_value = value

        while bitspan > 0:
            bytelist.append(value & 0xFF)
            value >>= 8
            bitspan -= 8

        # bytelist is little endian, so only reverse it if we're big endian
        if self.endianness == NumericRegion.BIG_ENDIAN:
            bytelist = bytelist[::-1]

        bitspan_content = bytelist_to_bitlist(bytelist)

        # truncate the binary list to the current bitspan
        self.write_bits(bitspan_content[-self.bitspan:])

    def __int__(self):
        return self.get_value()

    @classmethod
    def static_declaration(cls, **kwargs):
        kwargs.setdefault('endianness', cls.ENDIANNESS)
        kwargs.setdefault('signage', cls.SIGNAGE)
        kwargs.setdefault('value', cls.VALUE)

        super_class = super(NumericRegion, cls).static_declaration(**kwargs)

        class StaticNumericRegion(super_class):
            ENDIANNESS = kwargs['endianness']
            SIGNAGE = kwargs['signage']
            VALUE = kwargs['value']

        return StaticNumericRegion

# technically NumericRegions -are- bitfields, so this is just syntactic sugar.
# though the way they're parsed means we need to set it to BIG_ENDIAN
class Bitfield(NumericRegion):
    ENDIANNESS = NumericRegion.BIG_ENDIAN

class Byte(NumericRegion):
    BITSPAN = 8

class Word(NumericRegion):
    BITSPAN = 16

class Dword(NumericRegion):
    BITSPAN = 32

class Qword(NumericRegion):
    BITSPAN = 64

class CharError(NumericRegionError):
    pass

class Char(Byte):
    def get_char_value(self):
        return chr(self.get_value())

    def set_char_value(self, char):
        if not isinstance(char, basestring):
            raise CharError('input value must be a string')

        if len(char) > 1:
            raise CharError('input string can only be one character long')

        self.set_value(ord(char))

class WcharError(NumericRegionError):
    pass

class Wchar(Word):
    def get_wchar_value(self):
        return ''.join(map(chr, self.read_bytes_from_bits(2))).decode('utf-16')

    def set_wchar_value(self, wchar):
        if not isinstance(wchar, unicode):
            raise WcharError('input value must be a unicode string')

        if len(wchar) > 1:
            raise WcharError('input string can only be one character long')

        self.write_bits_from_bytes(map(ord, wchar.encode('utf-16be')))

class DataDeclarationError(ParanoiaError):
    pass

class DataDeclaration:
    BASE_CLASS = None
    ARGS = None

    def __init__(self, **kwargs):
        self.base_class = kwargs.setdefault('base_class', self.BASE_CLASS)

        if self.base_class is None:
            raise DataDeclarationError('base_class cannot be None')

        self.args = kwargs.setdefault('args', self.ARGS)

        if self.args is None:
            self.args = dict()

        if not isinstance(self.args, dict):
            raise DataDeclarationError('args must be a dictionary object')

    def instantiate(self, memory_base, bitshift=0):
        # make a copy of our argument instantiation
        arg_dict = dict(self.args.items()[:])
        arg_dict['memory_base'] = memory_base
        arg_dict['bitshift'] = bitshift

        return self.base_class(**arg_dict)

    def bitspan(self):
        if not self.args.has_key('bitspan'):
            return self.base_class.static_bitspan()

        return self.args['bitspan']

class DataListError(ParanoiaError):
    pass

class DataList(MemoryRegion):
    DECLARATIONS = None

    def __init__(self, **kwargs):
        self.declarations = kwargs.setdefault('declarations', self.DECLARATIONS)

        if self.declarations is None:
            self.declarations = list()

        if not isinstance(self.declarations, list):
            raise DataListError('declarations must be a list of DataDeclaration objects')

        self.memory_base = kwargs.setdefault('memory_base', self.MEMORY_BASE)

        if self.memory_base is None:
            raise DataListError('memory_base cannot be None')

        self.bitshift = kwargs.setdefault('bitshift', self.BITSHIFT)

        self.declaration_offsets = dict()
        self.calculate_offsets()

        kwargs['bitspan'] = self.bitspan
        MemoryRegion.__init__(self, **kwargs)

    def calculate_offsets(self, start_from=0):
        # truncate the declaration offsets to only that which currently exist
        declarative_length = len(self.declarations)
        self.declaration_offsets = dict(filter(lambda x: x[0] < declarative_length, self.declaration_offsets.items()))

        if start_from > 0:
            list_bitspan = sum(map(lambda x: self.declaration_offsets[x]['bitspan'], range(0, start_from)))
        else:
            list_bitspan = 0

        for i in range(start_from, len(self.declarations)):
            bitspan = self.declarations[i].bitspan()
            list_bitspan += bitspan

            offset_dict = dict()
            offset_dict['bitspan'] = bitspan

            if i == 0:
                offset_dict['memory_base'] = self.memory_base
                offset_dict['bitshift'] = self.bitshift
            else:
                # FIXME bitfields are aligned in a strange way. more research needs
                # FIXME to be done to figure out how to properly align them.

                previous_offset = self.declaration_offsets[i-1]
                previous_shift = previous_offset['bitshift']
                previous_span = previous_offset['bitspan']
                previous_base = previous_offset['memory_base']

                shift_and_span = previous_shift + previous_span

                new_shift = shift_and_span % 8
                new_base = previous_base + (shift_and_span / 8)

                offset_dict['bitshift'] = new_shift
                offset_dict['memory_base'] = new_base

            self.declaration_offsets[i] = offset_dict
            
        self.bitspan = list_bitspan

    def append_declaration(self, declaration):
        self.insert_declaration(len(self.declarations), declaration)

    def insert_declaration(self, index, declaration):
        if abs(index) > len(self.declarations):
            raise DataListError('index out of range')

        if not isinstance(declaration, DataDeclaration):
            raise DataListError('declaration must implement DataDeclaration')

        # even though negative indexes can insert just fine with python lists, we
        # adjust the negative index for the call to calculate_offsets.
        if index < 0:
            index += len(self.declarations)

        self.declarations.insert(index, declaration)
        self.calculate_offsets(index)

    def remove_declaration(self, index):
        if abs(index) > len(self.declarations):
            raise DataListError('index out of range')

        # even though negative indexes can remove just fine with python lists, we
        # adjust the negative index for the call to calculate_offsets.
        if index < 0:
            index += len(self.declarations)

        self.declarations.pop(index)

        if index == 0:
            self.calculate_offsets()
        else:
            self.calculate_offsets(index-1)

    def instantiate(self, index):
        if abs(index) > len(self.declarations):
            raise DataListError('index out of range')

        if index < 0:
            index += len(self.declarations)

        if not self.declaration_offsets.has_key(index):
            raise DataListError('offset for index not parsed')

        memory_base = self.declaration_offsets[index]['memory_base']
        bitshift = self.declaration_offsets[index]['bitshift']

        instance = self.declarations[index].instantiate(memory_base, bitshift)

        return instance

    # TODO def __getitem__

    @classmethod
    def static_bitspan(cls):
        if not cls.DECLARATIONS:
            raise DataListError('no static declarations to parse bitspan from')

        # FIXME this doesn't accomodate for odd bitfield alignment.
        # FIXME see calculate_offsets.
        return sum(map(DataDeclaration.bitspan, cls.DECLARATIONS))

    @classmethod
    def static_declaration(cls, **kwargs):
        kwargs.setdefault('declarations', cls.DECLARATIONS)

        super_class = super(DataList, cls).static_declaration(**kwargs)

        class StaticDataList(super_class):
            DECLARATIONS = kwargs['declarations']

        return StaticDataList

class DataArrayError(DataListError):
    pass

class DataArray(DataList):
    BASE_CLASS = None
    ELEMENTS = 0

    def __init__(self, **kwargs):
        self.base_class = kwargs.setdefault('base_class', self.BASE_CLASS)
        self.elements = kwargs.setdefault('elements', self.ELEMENTS)

        if self.elements == 0:
            raise DataArrayError('elements cannot be 0')

        kwargs['declarations'] = [DataDeclaration(base_class=self.base_class) for i in xrange(self.elements)]

        DataList.__init__(self, **kwargs)

    def parse_elements(self):
        if self.elements < len(self.declarations):
            self.declarations = self.declarations[:self.elements]
            self.calculate_offsets(len(self.declarations)) # truncate declaration_offsets
        elif self.elements > len(self.declarations):
            old_length = len(self.declarations)
            element_delta = self.elements - old_length

            for i in xrange(element_delta):
                self.declarations.append(DataDeclaration(base_class=self.base_class))
            self.calculate_offsets(old_length)

    def __setattr__(self, attr, value):
        if attr == 'elements':
            if self.__dict__.has_key('elements'):
                old_value = self.__dict__['elements']
                self.__dict__['elements'] = value

                if not old_value == value:
                    self.parse_elements()
            else:
                self.__dict__[attr] = value
        else:
            super(DataArray, self).__setattr__(attr, value)

    @classmethod
    def static_bitspan(cls):
        if cls.BASE_CLASS is None:
            raise DataArrayError('no base class to get base bitspan from')

        base_bitspan = cls.BASE_CLASS.static_bitspan()
        return base_bitspan * cls.ELEMENTS

    @classmethod
    def static_declaration(cls, **kwargs):
        kwargs.setdefault('base_class', cls.BASE_CLASS)
        kwargs.setdefault('elements', cls.ELEMENTS)

        if not kwargs['base_class'] is None and kwargs['elements'] > 0:
            kwargs['declarations'] = [DataDeclaration(base_class=kwargs['base_class']) for i in xrange(kwargs['elements'])]

        super_class = super(DataArray, cls).static_declaration(**kwargs)

        class StaticDataArray(super_class):
            BASE_CLASS = kwargs['base_class']
            ELEMENTS = kwargs['elements']

        return StaticDataArray

class DataStructureError(DataListError):
    pass

class DataStructure(DataList):
    STRUCT_DECLARATION = None

    def __init__(self, **kwargs):
        struct_declaration = kwargs.setdefault('struct_declaration', self.STRUCT_DECLARATION)

        if struct_declaration is None or not getattr(struct_declaration, '__iter__', None):
            raise DataStructureError('struct_declaration must be a sequence of names and DataDeclarations')

        self.parse_struct_declarations(struct_declaration)
        kwargs['declarations'] = self.declarations # for initializing bitspan

        DataList.__init__(self, **kwargs)

    def parse_struct_declarations(self, declarations):
        self.declarations = list()
        self.struct_map = dict()

        for struct_pair in declarations:
            if not len(struct_pair) == 2 or not isinstance(struct_pair[0], basestring) or not isinstance(struct_pair[1], DataDeclaration):
                raise DataStructureError('struct_declaration element must be a pair consisting of a string and a DataDeclaration.')
            
            name, declaration = struct_pair
            index = len(self.declarations)
            self.declarations.append(declaration)
            
            if self.struct_map.has_key(name):
                raise DataStructureError('%s already defined in structure' % name)

            self.struct_map[name] = index

        # XXX HACK bypass the potential for this function not to be there on init
        #if getattr(self, 'calculate_offsets', None):
        #    self.calculate_offsets()

    def __getattr__(self, attr):
        struct_map = self.__dict__['struct_map']

        if self.__dict__.has_key(attr):
            return self.__dict__[attr]
        elif struct_map.has_key(attr):
            index = struct_map[attr]
            return self.instantiate(index)
        else:
            raise AttributeError(attr)

    @classmethod
    def static_bitspan(cls):
        return sum(map(lambda x: x[1].bitspan(), cls.STRUCT_DECLARATION))

    @classmethod
    def simple(cls, declarations):
        new_struct_declaration = list()

        if not getattr(declarations, '__iter__', None):
            raise DataStructureError('declarations must be a sequence of names, a base class and optional arguments')

        if len(declarations) == 0:
            raise DataStructureError('empty declaration list given')

        for declaration in declarations:
            if not len(declaration) == 2 and not len(declaration) == 3:
                raise DataStructureError('simple declaration item has invalid arguments')

            if not isinstance(declaration[0], basestring):
                raise DataStructureError('first argument of the declaration must be a string')

            if not issubclass(declaration[1], MemoryRegion):
                raise DataStructureError('second argument must be a base class implementing MemoryRegion')

            if len(declaration) == 3 and not isinstance(declaration[2], dict):
                raise DataStructureError('optional third argument must be a dictionary of arguments')
                
            if not len(declaration) == 3:
                args = dict()
            else:
                args = declaration[2]

            new_struct_declaration.append([declaration[0]
                                          ,DataDeclaration(base_class=declaration[1]
                                                          ,args=args)])
        
        class SimplifiedDataStructure(cls):
            STRUCT_DECLARATION = new_struct_declaration

        return SimplifiedDataStructure
