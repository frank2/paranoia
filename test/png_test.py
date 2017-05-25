#!/usr/bin/env python

from paranoia.base.disk import disk_handle
from paranoia.meta import List, ListError
from parnaoia.types import Dword, Qword

class PNGError(ListError):
    pass

class PNGHeader(Qword):
    MAGIC = 0x0a1a0a0d474e5089

class PNGFile(List):
    FILENAME = None
    
    def __init__(self, **kwargs):
        self.filename = kwargs.setdefault('filename', self.FILENAME)
        self.address = kwargs.setdefault('address', self.ADDRESS)

        if not self.filename is None and self.address is None:
            mode = kwargs.setdefault('mode', 'r')
            self.handle = disk_handle(self.filename, mode)
        else:
            self.handle = None

        super(PNGFile, self).__init__(**kwargs)

    def __del__(self):
        self.handle.close(True)
        
