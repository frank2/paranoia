#!/usr/bin/env python

from paranoia.base import paranoia_agent

try:
    import __builtin__
except ImportError: # python3
    import builtins as __builtin__

__all__ = ['AddressError', 'Address']

class AddressError(paranoia_agent.ParanoiaError):
    pass

class Address(paranoia_agent.ParanoiaAgent):
    ALLOCATION = None
    OFFSET = 0

    def __init__(self, **kwargs):
        long = getattr(__builtin__, 'long', None)

        if long is None: # python 3
            long = int
            
        self.allocation = kwargs.setdefault('allocation', self.ALLOCATION)
        self.offset = kwargs.setdefault('offset', self.OFFSET)

        if not isinstance(self.offset, (int, long)):
            raise AddressError('offset must be an int or a long')

    def value(self):
        if not self.allocation is None:
            return self.allocation.address + self.offset

        return self.offset

    def fork(self, offset):
        return Address(offset=self.offset+offset, allocation=self.allocation)

    def __int__(self):
        return self.value()
