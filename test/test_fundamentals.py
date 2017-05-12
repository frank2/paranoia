#!/usr/bin/env python

import unittest

from paranoia.fundamentals import *

class FundamentalsModuleTest(unittest.TestCase):
    def test_crt(self):
        self.assertNotEqual(malloc, None)
        self.assertNotEqual(realloc, None)
        self.assertNotEqual(free, None)
        self.assertNotEqual(memset, None)
        self.assertNotEqual(memmove, None)

    def test_alignment(self):
        self.assertFalse(aligned(4, 8))
        self.assertTrue(aligned(0, 8))
        self.assertTrue(aligned(16, 8))

        self.assertEqual(alignment_delta(4, 8), 4)
        self.assertEqual(alignment_delta(2, 8), 6)
        self.assertEqual(alignment_delta(0, 8), 0)

        self.assertEqual(align(2, 8), 8)
        self.assertEqual(align(12, 8), 16)
        self.assertEqual(align(16, 8), 16)

    def test_list_conversions(self):
        self.assertEqual(bitlist_to_bytelist([1, 1, 0, 0, 1, 1, 0, 0]), [0b11001100])
        self.assertEqual(bitlist_to_bytelist([1, 1, 0, 0]), [0b1100])
        self.assertEqual(bitlist_to_bytelist([1, 1, 0, 0, 1, 1, 0, 0] * 4), [0b11001100] * 4)

        self.assertEqual(bytelist_to_bitlist([0b11001100]), [1, 1, 0, 0, 1, 1, 0, 0])
        self.assertEqual(bytelist_to_bitlist([0b11001100]*4), [1, 1, 0, 0, 1, 1, 0, 0] * 4)
        self.assertEqual(bytelist_to_bitlist([0b1100]), [0, 0, 0, 0, 1, 1, 0, 0])

        self.assertEqual(bitlist_to_numeric([1, 1, 0, 0]), 0xC)
        self.assertEqual(bitlist_to_numeric([1, 1, 0, 0] * 2), 0xCC)
        self.assertEqual(bitlist_to_numeric([1, 1, 0, 0] * 4), 0xCCCC)
        
        self.assertEqual(numeric_to_bitlist(0xC), [1, 1, 0, 0])
        self.assertEqual(numeric_to_bitlist(0xCC), [1, 1, 0, 0] * 2)
        self.assertEqual(numeric_to_bitlist(0xCCCC), [1, 1, 0, 0] * 4)

    def test_dict_merge(self):
        left = {'a': 'b'}
        right = {'a': 'b'}
        dict_merge(left, right)
        self.assertEqual({'a': 'b'}, left)

        left = {'a': 'b'}
        right = {'a': 'c'}
        dict_merge(left, right)
        self.assertEqual({'a': 'b'}, left)

        left = {'a': 'b'}
        right = {'c': 'd'}
        dict_merge(left, right)
        self.assertEqual({'a': 'b', 'c': 'd'}, left)

    def test_string_address(self):
        import ctypes

        key = 'ADNU'
        found_offset = ctypes.string_at(id(key), 256).index(key)

        self.assertEqual(found_offset, string_offset)
        self.assertEqual(key, ctypes.string_at(id(key)+found_offset))
