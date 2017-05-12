#!/usr/bin/env python

import unittest

from paranoia.fundamentals import *
from paranoia.base.address import Address, AddressError
from paranoia.base.allocator import AllocationError, heap

class AddressModuleTest(unittest.TestCase):
    def test_constructor(self):
        string_object = 'PARANOiA'
        string_addr = string_address(string_object)
        addr_obj = Address(offset=string_addr) # should allocate from memory

        self.assertEqual(int(addr_obj), string_addr)

        allocation = heap.allocate(16)
        addr_obj = Address(allocation=allocation, offset=0)

        self.assertEqual(int(addr_obj), allocation.id)

        addr_obj = Address(allocation=allocation, offset=8)
            
        self.assertEqual(int(addr_obj), allocation.id+8)

        bad_obj = Address(allocation=allocation, offset=20)
        self.assertFalse(bad_obj.valid())

    def test_object(self):
        string_object = 'PARANOiA'
        string_addr = string_address(string_object)
        address_object = Address(offset=string_addr) # allocates in memory

        self.assertEqual(int(address_object), string_addr)
        self.assertEqual(address_object.read_string(len(string_object)), string_object)
