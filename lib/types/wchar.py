#!/usr/bin/env python

try:
    import __builtin__
except ImportError: # python3
    import builtins as __builtin__

from paranoia.base import numeric_region
from paranoia.meta import array
from paranoia.types import word

__all__ = ['WcharError', 'Wchar', 'WcharArray']

class WcharError(numeric_region.NumericRegionError):
    pass

class Wchar(word.Word):
    def get_wchar_value(self):
        return self.read_bytestring(2).decode('utf-16be')

    def set_wchar_value(self, wchar):
        # python3 doesn't have a unicode type-- strings are, in fact, unicode.
        # so rejoin israel and palestine by doing the needful to a unicode
        # object
        unicode = getattr(__builtin__, 'unicode', None)

        if unicode is None: # python3
            unicode = str
            
        if not isinstance(wchar, (str, unicode)):
            raise WcharError('input value must be a unicode string')

        if len(wchar) > 1:
            raise WcharError('input string can only be one character long')

        encoded = wchar.encode('utf-16be')

        if isinstance(encoded, str): # python 2
            encoded = list(map(ord, encoded))
        else:
            encoded = list(encoded)

        self.write_bits_from_bytes(encoded)

class WcharArray(array.Array):
    BASE_CLASS = Wchar
