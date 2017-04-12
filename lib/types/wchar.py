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
    def get_char_value(self):
        return unichr(self.get_value()).encode('utf-16be').decode('utf-16be')

    def set_char_value(self, wchar):
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

        self.set_value(ord(wchar))

class WcharArray(array.Array):
    BASE_DECLARATION = Wchar
