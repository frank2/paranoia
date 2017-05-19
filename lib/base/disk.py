#!/usr/bin/env python

from paranoia.base.paranoia_agent import ParanoiaAgent, ParanoiaError
from paranoia.base.allocator import VirtualAllocator

class DiskError(ParanoiaError):
    pass

class DiskManager(ParanoiaAgent):
    def __init__(self, **kwargs):
        self.files = dict()
        self.allocators = dict()

    def open(self, filename, mode, buffer=False):
        fp = open(filename, mode)
        self.files[fp.fileno()] = fp
        self.allocators = VirtualAllocator(buffer=buffer, base_address=None)

    def close(self, fileno):
        if not fileno in self.files:
            raise DiskError('fileno not being managed')

        self.files[fileno].close()
        del self.files[fileno]
        del self.allocators[fileno]

disk = DiskManager()
