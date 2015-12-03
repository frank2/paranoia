#!/usr/bin/env python
# -*- coding: utf-8 -*-

import cProfile
import ctypes
import os
import sys

from paranoia import *
list = __builtins__.list # paranoia clobbers list on import of everything
float = __builtins__.float # paranoia also clobbers float

ALLOCATOR = Allocator()

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

    init_string = 'MemoryRegion test'
    region = MemoryRegion(string_data=init_string)

    # run basic assertions
    assert region.bitspan == len(init_string)*8
    assert region.read_bytes(len(init_string)) == map(ord, init_string)
    assert region.read_bytes(len(init_string)-1, 1) == map(ord, init_string[1:])
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

    misaligned = MemoryRegion(memory_base=region.memory_base, bitspan=12)
    assert misaligned.bitspan == 12
    assert misaligned.bytespan() == 2
    misaligned.bitshift = 5
    assert misaligned.bitspan == 12
    assert misaligned.shifted_bitspan() == 17
    assert misaligned.shifted_bytespan() == 3
    print '[MemoryRegion.alignment: PASS]'

def test_NumericRegion():
    print '[test_NumericRegion]'

    region = NumericRegion(bitspan=4*8)
    region.set_value(0x80)
    assert region.get_value() == 0x80
    region.endianness = NumericRegion.BIG_ENDIAN
    assert region.get_value() == 0x80000000
    region.endianness = NumericRegion.LITTLE_ENDIAN
    region.bitspan = 31
    assert region.get_value() == 0x40
    region.endianness = NumericRegion.BIG_ENDIAN
    assert region.get_value() == 0x40000000
    print '[NumericRegion.get_value: PASS]'

    region.bitspan = 32
    region.endianness = NumericRegion.LITTLE_ENDIAN
    region.set_value(0x88443322)
    assert region.get_value() == 0x88443322
    region.bitspan = 16
    region.set_value(0x5566)
    assert region.get_value() == 0x5566
    region.bitspan = 32
    region.endianness = NumericRegion.BIG_ENDIAN
    region.set_value(0x88443322)
    assert region.get_value() == 0x88443322
    assert region.read_bytes(4) == [136, 68, 51, 34]
    region.bitspan = 16
    region.set_value(0x5566)
    assert region.get_value() == 0x5566
    print '[NumericRegion.set_value: PASS]'

    region.signage = NumericRegion.SIGNED
    region.bitspan = 32
    region.set_value(0xFFFFFFFF)
    assert region.get_value() == -1
    region.set_value(-2)
    assert region.get_value() == -2
    print '[NumericRegion.SIGNED: PASS]'

def test_NumericTypes():
    print '[test_Bitfield]'
    bitfield_object = Bitfield(bitspan=4)
    bitfield_object.set_value(0x22) # test bit-level truncation
    assert bitfield_object.get_value() == 0x2
    print '[Bitfield: PASS]'

    print '[test_Byte]'
    byte_object = Byte()
    byte_object.set_value(0x66)
    assert byte_object.get_value() == 0x66
    print '[Byte: PASS]'

    print '[test_Word]'
    word_object = Word()
    word_object.set_value(0x7777)
    assert word_object.get_value() == 0x7777
    print '[Word: PASS]'

    print '[test_Dword]'
    dword_object = Dword()
    dword_object.set_value(0x88888888)
    assert dword_object.get_value() == 0x88888888
    print '[Dword: PASS]'

    print '[test_Qword]'
    qword_object = Qword()
    qword_object.set_value(0x2222222222222222)
    assert qword_object.get_value() == 0x2222222222222222
    print '[Qword: PASS]'

def test_Float():
    print '[test_Float]'

    floats = [2.625, -4.75, 0.40625, -12.0, 1.7, -1313.3125, 0.1015625, 39887.5625, 728.25]

    for f in floats:
        double_obj = Double(value=f)
        assert float(double_obj) == f

    print '[Float: PASS]'
        
def test_CharTypes():
    # allocate a string
    c_address = ALLOCATOR.allocate_string('Character Buffer')
    c_string = ALLOCATOR.address_map[c_address]

    print '[test_Char]'
    char_object = Char(memory_base=c_address)
    assert char_object.get_char_value() == 'C'
    print '[Char.get_char_value: PASS]'

    char_object.set_char_value('D')
    assert char_object.get_char_value() == 'D'
    print '[Char.set_char_value: PASS]'

    print '[test_Wchar]'

    wchar_object = Wchar(memory_base=c_address)
    wchar_object.set_wchar_value(u'한')
    assert wchar_object.get_wchar_value() == u'한'

    print '[Wchar: PASS]'

    ALLOCATOR.deallocate(c_address)

def test_Declaration():
    # allocate a string
    c_address = ALLOCATOR.allocate_string('Character Buffer')
    c_string = ALLOCATOR.address_map[c_address]

    print '[test_Declaration]'
    declaration = Declaration(base_class=Byte)
    instantiated = declaration.instantiate(c_address)
    assert isinstance(instantiated, Byte)
    assert instantiated.memory_base == c_address
    assert instantiated.get_value() == ord('C')

    instantiated = declaration.instantiate(c_address, 4)
    assert instantiated.memory_base == c_address
    assert instantiated.bitshift == 4
    print '[Declaration.instantiate: PASS]'

    assert declaration.bitspan() == 8

    declaration = Declaration(base_class=Bitfield, args={'bitspan': 4})
    assert declaration.bitspan() == 4
    print '[Declaration.bitspan: PASS]'

    ALLOCATOR.deallocate(c_address)

def test_List():
    # allocate a string
    c_address = ALLOCATOR.allocate_string("\x00\x01\x01\x02\x02\x02\x02\x03\x03\x03\x03\x03\x03\x03\x03")
    c_string = ALLOCATOR.address_map[c_address]

    print '[test_List]'
    data_list = List(declarations=[Declaration(base_class=Byte)
                                   ,Declaration(base_class=Word)
                                   ,Declaration(base_class=Dword)]
                         ,memory_base=c_address)
    
    assert data_list.declaration_offsets[0]['memory_base'] == c_address
    assert data_list.declaration_offsets[1]['memory_base'] == c_address+1
    assert data_list.declaration_offsets[2]['memory_base'] == c_address+3

    byte_item = data_list.instantiate(0)
    assert isinstance(byte_item, Byte)
    assert byte_item.get_value() == 0
    assert byte_item.memory_base == c_address
    assert byte_item.parent_region == data_list

    word_item = data_list.instantiate(1)
    assert isinstance(word_item, Word)
    assert word_item.get_value() == 0x101
    assert word_item.memory_base == c_address+1

    dword_item = data_list.instantiate(2)
    assert isinstance(dword_item, Dword)
    assert dword_item.get_value() == 0x2020202
    assert dword_item.memory_base == c_address+3
    print '[List.instantiate: PASS]'

    data_list.append_declaration(Declaration(base_class=Qword))
    assert data_list.declaration_offsets[3]['memory_base'] == c_address+7
    qword_item = data_list.instantiate(3)
    assert isinstance(qword_item, Qword)
    assert qword_item.get_value() == 0x303030303030303
    assert qword_item.memory_base == c_address+7
    print '[List.append_declaration: PASS]'

    data_list.remove_declaration(2)
    qword_item = data_list.instantiate(2)
    assert isinstance(qword_item, Qword)
    assert qword_item.memory_base == c_address+3
    print '[List.remove_declaration: PASS]'

    data_list.insert_declaration(1, Declaration(base_class=Dword))
    dword_item = data_list.instantiate(1)
    assert isinstance(dword_item, Dword)
    assert dword_item.memory_base == c_address+1
    assert data_list.declaration_offsets[2]['memory_base'] == c_address+5
    print '[List.insert_declaration: PASS]'

    ALLOCATOR.deallocate(c_address)

def test_Array():
    c_address = ALLOCATOR.allocate(20)

    # TODO what's the test-case for an array of bitfields?
    print '[test_Array]'
    byte_array = Array(base_class=Byte
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
    print '[Array.parse_elements: PASS]'

    class SizeTestClass(Array):
        BASE_CLASS = Byte

    StaticSizeClass = SizeTestClass.static_size(20)
    byte_array = StaticSizeClass(memory_base=c_address)
    assert len(byte_array.declarations) == 20
    assert byte_array.instantiate(5).get_value() == 0x50
    print '[Array.static_size: PASS]'

    ALLOCATOR.deallocate(c_address)

def test_String():
    print '[test_String]'
    
    test_string = 'string\x00data\x00here\x00'
    char_array = CharArray(elements=len(test_string)
                           ,string_data=test_string)
    string_obj = String(memory_base=char_array.memory_base)
    assert str(string_obj) == 'string'
    string_obj[6].set_char_value(' ')
    assert str(string_obj) == 'string data'
    string_obj.set_value('str data')
    assert str(string_obj) == 'str data'

    print '[String: PASS]'

def test_Structure():
    print '[test_Structure]'

    array_class = Array.static_declaration(base_class=Byte, elements=21)

    nested_structure = Structure.simple([
        ('dword_obj', Dword)
        ,('word_obj', Word)
        ,('byte_obj', Byte)])

    structure_class = Structure.simple([
        ('byte_obj', Byte)
        ,('word_obj', Word, {'value': 0x505})
        ,('dword_obj', Dword)
        ,('qword_obj', Qword)
        ,('bitfield_1', Bitfield, {'bitspan': 2})
        ,('bitfield_2', Bitfield, {'bitspan': 4})
        ,('array_obj', array_class)
        ,('nested_obj', nested_structure)
        ,(None, Structure.simple([
            ('anon_byte_1', Byte)
            ,('anon_word_1', Word)
            ,('anon_dword_1', Dword)]))
        ,(None, Structure.simple([
            ('anon_byte_2', Byte)
            ,('anon_word_2', Word)
            ,('anon_dword_2', Dword)]))])

    struct_size = structure_class.static_bitspan() / 8
    c_address = ALLOCATOR.allocate(struct_size)
    structure_instance = structure_class(memory_base=c_address)

    assert isinstance(structure_instance.word_obj, Word)
    assert structure_instance.word_obj.get_value() == 0x505

    byte_item = structure_instance.array_obj.instantiate(5)
    byte_item.set_value(0x90)
    assert structure_instance.array_obj.instantiate(5).get_value() == 0x90

    nested_word = structure_instance.nested_obj.word_obj
    nested_word.set_value(0x505)
    assert structure_instance.nested_obj.word_obj.get_value() == 0x505

    qword_obj = structure_instance.qword_obj
    qword_obj.set_value(0x554e4441554e4441)
    array_obj = structure_instance.array_obj
    array_obj[0].set_value(0x44)
    bitfield_1 = structure_instance.bitfield_1
    bitfield_2 = structure_instance.bitfield_2
    bitfield_1.set_value(0)
    bitfield_2.set_value(0)
    assert structure_instance.qword_obj.get_value() == 0x554e4441554e4441
    assert structure_instance.array_obj[0].get_value() == 0x44
    assert structure_instance.bitfield_1.bitshift == 0
    assert structure_instance.bitfield_2.bitshift == 2
    assert structure_instance.bitfield_1.memory_base == structure_instance.bitfield_2.memory_base
    
    bitfield_1.set_value(1)
    assert structure_instance.bitfield_1.get_value() == 1
    assert structure_instance.bitfield_2.get_value() == 0

    bitfield_1.set_value(4)
    assert structure_instance.bitfield_1.get_value() == 0

    bitfield_1.set_value(2)
    bitfield_2.set_value(10)
    assert structure_instance.bitfield_1.get_value() == 2
    assert structure_instance.bitfield_2.get_value() == 10
    assert structure_instance.qword_obj.get_value() == 0x554e4441554e4441
    assert structure_instance.array_obj[0].get_value() == 0x44

    anon_dword = structure_instance.anon_dword_1
    anon_dword.set_value(0x42)
    assert structure_instance.anon_dword_1.get_value() == 0x42

    anon_dword = structure_instance.anon_dword_2
    anon_dword.set_value(0x42)
    assert structure_instance.anon_dword_2.get_value() == 0x42

    print '[Structure: PASS]'

def test_Union():
    print '[test_Union]'

    array_class = Array.static_declaration(base_class=Byte, elements=7)

    nested_structure = Structure.simple([
        ('dword_obj', Dword)
        ,('word_obj', Word)
        ,('byte_obj', Byte)])

    union_class = Union.simple([
        ('array', array_class)
        ,('structure', nested_structure)
        ,('qword', Qword)
        ,('dword', Dword)
        ,('word', Word)
        ,('byte', Byte)
        ,('bitfield', Bitfield, {'bitspan': 8*8+1})])

    union_size = union_class.static_bitspan()
    assert union_size == 65

    union_size = union_class.static_bytespan()
    assert union_size == 9

    union_instance = union_class()
    union_instance.array[0].set_value(0x42)
    assert union_instance.structure.dword_obj.get_value() == 0x42

    union_instance.structure.word_obj.set_value(0x42)
    assert union_instance.array[4].get_value() == 0x42
    assert union_instance.qword.get_value() == 0x4200000042

    # FIXME not sure if this test is correct.
    union_instance.structure.byte_obj.set_value(0x42)
    assert union_instance.array[6].get_value() == 0x42
    assert union_instance.bitfield.get_value() == 0x8400000084008400

    print '[Union: PASS]'

def test_Pointer():
    print '[test_Pointer]'

    dword_obj = Dword()
    dword_obj.set_value(0x32323232)

    qword_obj = Qword()
    qword_obj.set_value(0x6464646464646464)

    dword_array = Array(base_class=Dword
                        ,elements=20)

    dword_array[10].set_value(0x42424242)
    dword_array[0].set_value(0x21212121)

    if dword_obj.memory_base < 0xFFFFFFFF:
        pointer_class = Pointer32
    else:
        pointer_class = Pointer64

    pointer_32 = pointer_class.cast(Dword)()
    pointer_64 = pointer_class.cast(Qword)()

    pointer_32.set_value(dword_obj.memory_base)
    assert pointer_32.deref().get_value() == 0x32323232

    pointer_64.set_value(qword_obj.memory_base)
    assert pointer_64.deref().get_value() == 0x6464646464646464

    assert pointer_64.read_pointed_bytes(4) == [0x64, 0x64, 0x64, 0x64]
    pointer_64.write_pointed_bytes([0x32]*4, 4)
    assert int(pointer_64.deref()) == 0x3232323264646464

    array_pointer_front = pointer_class.cast(Dword)(value=dword_array.memory_base)
    array_pointer_middle = array_pointer_front + 10

    assert array_pointer_front.deref().get_value() == 0x21212121
    assert array_pointer_middle.deref().get_value() == 0x42424242
    assert (array_pointer_front+10).deref().get_value() == 0x42424242
    assert (array_pointer_middle-10).deref().get_value() == 0x21212121
    assert array_pointer_front[10].get_value() == 0x42424242
    assert array_pointer_middle[-10].get_value() == 0x21212121

    print '[Pointer: PASS]'

def main(*args):
    test_Allocator()
    test_MemoryRegion()
    test_NumericRegion()
    test_NumericTypes()
    test_CharTypes()
    test_Declaration()
    test_List()
    test_Array()
    test_String()
    test_Structure()
    test_Float()
    test_Union()
    test_Pointer()

if __name__ == '__main__':
    cProfile.run('main(*sys.argv[1:])')
