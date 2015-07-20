#!/usr/bin/env python
# -*- coding: utf-8 -*-

import cProfile
import ctypes
import os
import sys

import paranoia

ALLOCATOR = paranoia.Allocator()

def test_Allocator():
    byte_buffer = ALLOCATOR.allocate(20)
    assert ALLOCATOR.address_map.has_key(byte_buffer)
    assert len(ALLOCATOR.address_map[byte_buffer].raw) == 20

    string_buffer = ALLOCATOR.allocate_string('string')
    assert ALLOCATOR.address_map.has_key(string_buffer)
    assert len(ALLOCATOR.address_map[string_buffer].raw) == len('string\x00')

    ALLOCATOR.deallocate(string_buffer)
    ALLOCATOR.deallocate(byte_buffer)
    assert not ALLOCATOR.address_map.has_key(string_buffer)
    assert not ALLOCATOR.address_map.has_key(byte_buffer)

def test_MemoryRegion():
    print '[test_MemoryRegion]'

    # allocate a string
    c_address = ALLOCATOR.allocate_string('MemoryRegion test')
    c_string = ALLOCATOR.address_map[c_address]

    # initialize the region
    region = paranoia.MemoryRegion(memory_base=c_address, bitspan=len(c_string)*8)

    # run basic assertions
    assert region.read_bytes(len(c_string)) == map(ord, c_string.raw)
    assert region.read_bytes(len(c_string)-1, 1) == map(ord, c_string.raw[1:])
    print '[MemoryRegion.read_bytes: PASS]'

    assert region.read_bits_from_bytes(4) == [0, 1, 0, 0]
    assert region.read_bits_from_bytes(4, 4) == [1, 1, 0, 1]
    assert region.read_bits_from_bytes(4, 6) == [0, 1, 0, 1]
    print '[MemoryRegion.read_bits_from_bytes: PASS]'

    assert region.read_bytes_from_bits(8, 4) == [int('11010110', 2)]
    assert region.read_bytes_from_bits(6, 4) == [int('110101', 2)]
    print '[MemoryRegion.read_bytes_from_bits: PASS]'

    region.write_bytes([69, 72, 45, 54], 0)
    assert region.read_bytes(4) == [69, 72, 45, 54]
    region.write_bytes([69, 72, 45, 54], 4)
    assert region.read_bytes(4, 4) == [69, 72, 45, 54]
    region.write_bytes([77], 4)
    assert region.read_bytes(4, 4) == [77, 72, 45, 54]
    print '[MemoryRegion.write_bytes: PASS]'

    region.write_bits([1] * 4)
    assert region.read_bits_from_bytes(4) == [1] * 4
    region.write_bits([1] * 12, 6)
    assert region.read_bits_from_bytes(12, 6) == [1] * 12
    print '[MemoryRegion.write_bits: PASS]'

    ALLOCATOR.deallocate(c_address)

def test_NumericRegion():
    print '[test_NumericRegion]'

    # allocate a string
    c_address = ALLOCATOR.allocate_string('\x80\x00\x00\x00')
    c_string = ALLOCATOR.address_map[c_address]

    region = paranoia.NumericRegion(memory_base=c_address, bitspan=(len(c_string)-1)*8)
    assert region.get_value() == 0x80
    region.endianness = paranoia.NumericRegion.BIG_ENDIAN
    assert region.get_value() == 0x80000000
    region.endianness = paranoia.NumericRegion.LITTLE_ENDIAN
    region.bitspan = 31
    assert region.get_value() == 0x40
    region.endianness = paranoia.NumericRegion.BIG_ENDIAN
    assert region.get_value() == 0x40000000
    print '[NumericRegion.get_value: PASS]'

    region.bitspan = 32
    region.endianness = paranoia.NumericRegion.LITTLE_ENDIAN
    region.set_value(0x88443322)
    assert region.get_value() == 0x88443322
    region.bitspan = 16
    region.set_value(0x77995566)
    assert region.get_value() == 0x5566
    region.bitspan = 32
    region.endianness = paranoia.NumericRegion.BIG_ENDIAN
    region.set_value(0x88443322)
    assert region.get_value() == 0x88443322
    region.bitspan = 16
    region.set_value(0x77995566)
    assert region.get_value() == 0x5566
    print '[NumericRegion.set_value: PASS]'
    
    ALLOCATOR.deallocate(c_address)

def test_NumericTypes():
    c_address = ALLOCATOR.allocate(8)

    print '[test_Bitfield]'
    bitfield_object = paranoia.Bitfield(memory_base=c_address, bitspan=4)
    bitfield_object.set_value(0x22) # test bit-level truncation
    assert bitfield_object.get_value() == 0x2
    print '[Bitfield: PASS]'

    print '[test_Byte]'
    byte_object = paranoia.Byte(memory_base=c_address)
    byte_object.set_value(0x66)
    assert byte_object.get_value() == 0x66
    print '[Byte: PASS]'

    print '[test_Word]'
    word_object = paranoia.Word(memory_base=c_address)
    word_object.set_value(0x7777)
    assert word_object.get_value() == 0x7777
    print '[Word: PASS]'

    print '[test_Dword]'
    dword_object = paranoia.Dword(memory_base=c_address)
    dword_object.set_value(0x88888888)
    assert dword_object.get_value() == 0x88888888
    print '[Dword: PASS]'

    print '[test_Qword]'
    qword_object = paranoia.Qword(memory_base=c_address)
    qword_object.set_value(0x2222222222222222)
    assert qword_object.get_value() == 0x2222222222222222
    print '[Qword: PASS]'

    ALLOCATOR.deallocate(c_address)

def test_CharTypes():
    # allocate a string
    c_address = ALLOCATOR.allocate_string('Character Buffer')
    c_string = ALLOCATOR.address_map[c_address]

    print '[test_Char]'
    char_object = paranoia.Char(memory_base=c_address)
    assert char_object.get_char_value() == 'C'
    print '[Char.get_char_value: PASS]'

    char_object.set_char_value('D')
    assert char_object.get_char_value() == 'D'
    print '[Char.set_char_value: PASS]'

    # FIXME wchars are broken. run these tests another time.
    #print '[test_Wchar]'

    #wchar_object = paranoia.Wchar(memory_base=c_address)
    #wchar_object.set_wchar_value(u'한')
    #assert wchar_object.get_wchar_value() == u'한'

    ALLOCATOR.deallocate(c_address)

def test_DataDeclaration():
    # allocate a string
    c_address = ALLOCATOR.allocate_string('Character Buffer')
    c_string = ALLOCATOR.address_map[c_address]

    print '[test_DataDeclaration]'
    declaration = paranoia.DataDeclaration(base_class=paranoia.Byte)
    instantiated = declaration.instantiate(c_address)
    assert isinstance(instantiated, paranoia.Byte)
    assert instantiated.memory_base == c_address
    assert instantiated.get_value() == ord('C')

    instantiated = declaration.instantiate(c_address, 4)
    assert instantiated.memory_base == c_address
    assert instantiated.bitshift == 4
    print '[DataDeclaration.instantiate: PASS]'

    assert declaration.bitspan() == 8

    declaration = paranoia.DataDeclaration(base_class=paranoia.Bitfield, args={'bitspan': 4})
    assert declaration.bitspan() == 4
    print '[DataDeclaration.bitspan: PASS]'

    ALLOCATOR.deallocate(c_address)

def test_DataList():
    # allocate a string
    c_address = ALLOCATOR.allocate_string("\x00\x01\x01\x02\x02\x02\x02\x03\x03\x03\x03\x03\x03\x03\x03")
    c_string = ALLOCATOR.address_map[c_address]

    print '[test_DataList]'
    data_list = paranoia.DataList(declarations=[paranoia.DataDeclaration(base_class=paranoia.Byte)
                                               ,paranoia.DataDeclaration(base_class=paranoia.Word)
                                               ,paranoia.DataDeclaration(base_class=paranoia.Dword)]
                                 ,memory_base=c_address)
    
    assert data_list.declaration_offsets[0]['memory_base'] == c_address
    assert data_list.declaration_offsets[1]['memory_base'] == c_address+1
    assert data_list.declaration_offsets[2]['memory_base'] == c_address+3

    byte_item = data_list.instantiate(0)
    assert isinstance(byte_item, paranoia.Byte)
    assert byte_item.get_value() == 0
    assert byte_item.memory_base == c_address

    word_item = data_list.instantiate(1)
    assert isinstance(word_item, paranoia.Word)
    assert word_item.get_value() == 0x101
    assert word_item.memory_base == c_address+1

    dword_item = data_list.instantiate(2)
    assert isinstance(dword_item, paranoia.Dword)
    assert dword_item.get_value() == 0x2020202
    assert dword_item.memory_base == c_address+3
    print '[DataList.instantiate: PASS]'

    data_list.append_declaration(paranoia.DataDeclaration(base_class=paranoia.Qword))
    assert data_list.declaration_offsets[3]['memory_base'] == c_address+7
    qword_item = data_list.instantiate(3)
    assert isinstance(qword_item, paranoia.Qword)
    assert qword_item.get_value() == 0x303030303030303
    assert qword_item.memory_base == c_address+7
    print '[DataList.append_declaration: PASS]'

    data_list.remove_declaration(2)
    qword_item = data_list.instantiate(2)
    assert isinstance(qword_item, paranoia.Qword)
    assert qword_item.memory_base == c_address+3
    print '[DataList.remove_declaration: PASS]'

    data_list.insert_declaration(1, paranoia.DataDeclaration(base_class=paranoia.Dword))
    dword_item = data_list.instantiate(1)
    assert isinstance(dword_item, paranoia.Dword)
    assert dword_item.memory_base == c_address+1
    assert data_list.declaration_offsets[2]['memory_base'] == c_address+5
    print '[DataList.insert_declaration: PASS]'

    ALLOCATOR.deallocate(c_address)

def test_DataArray():
    c_address = ALLOCATOR.allocate(20)

    # TODO what's the test-case for an array of bitfields?
    print '[test_DataArray]'
    byte_array = paranoia.DataArray(base_class=paranoia.Byte
                                   ,elements=20
                                   ,memory_base=c_address)

    byte_object = byte_array.instantiate(5)
    assert byte_object.memory_base == c_address+5

    byte_object.set_value(0x50)
    assert byte_array.instantiate(5).get_value() == 0x50

    byte_array.elements = 10
    assert len(byte_array.declarations) == 10

    byte_array.elements = 15
    assert len(byte_array.declarations) == 15
    print '[DataArray.parse_elements: PASS]'

    ALLOCATOR.deallocate(c_address)

def test_DataStructure():
    print '[test_DataStructure]'

    array_class = paranoia.DataArray.static_declaration(base_class=paranoia.Byte, elements=20)

    nested_structure = paranoia.DataStructure.simple(
        [('dword_obj', paranoia.Dword)
         ,('word_obj', paranoia.Word)
         ,('byte_obj', paranoia.Byte)])

    structure_class = paranoia.DataStructure.simple(
        [('byte_obj', paranoia.Byte)
         ,('word_obj', paranoia.Word, {'value': 0x505})
         ,('dword_obj', paranoia.Dword)
         ,('qword_obj', paranoia.Qword)
         ,('array_obj', array_class)
         ,('nested_obj', nested_structure)])

    struct_size = structure_class.static_bitspan() / 8
    c_address = ALLOCATOR.allocate(struct_size)
    structure_instance = structure_class(memory_base=c_address)

    assert isinstance(structure_instance.word_obj, paranoia.Word)
    assert structure_instance.word_obj.get_value() == 0x505

    byte_item = structure_instance.array_obj.instantiate(5)
    byte_item.set_value(0x90)
    assert structure_instance.array_obj.instantiate(5).get_value() == 0x90

    nested_word = structure_instance.nested_obj.word_obj
    nested_word.set_value(0x505)
    assert structure_instance.nested_obj.word_obj.get_value() == 0x505

def main(*args):
    test_Allocator()
    test_MemoryRegion()
    test_NumericRegion()
    test_NumericTypes()
    test_CharTypes()
    test_DataDeclaration()
    test_DataList()
    test_DataArray()
    test_DataStructure()

if __name__ == '__main__':
    cProfile.run('main(*sys.argv[1:])')
