#!/usr/bin/env python

import binascii

from paranoia.base.disk import disk_handle
from paranoia.base.size import Size
from paranoia.meta import List, ListError, SizeHint
from paranoia.types import String, Dword, Qword, ByteArray, Structure

class PNGError(ListError):
    pass

class PNGHeader(Qword):
    MAGIC = 0x0a1a0a0d474e5089

class PNGChunk(Structure):
    FIELDS = [('length', SizeHint.declare(size=Size(bits=32)
                                          ,endianness=SizeHint.BIG_ENDIAN
                                          ,field_name='chunk_data'
                                          ,action='set_elements'))
              ,('chunk_type', String.declare(zero_terminated=False
                                             ,elements=4
                                             ,static=True))
              ,('chunk_data', ByteArray)
              ,('crc', Dword.declare(endianness=Dword.BIG_ENDIAN))]

    def calculate_checksum(self):
        length = int(self['length'])
        type_address = self['chunk_type'].address
        data = type_address.read_bytestring(size=length+4)

        return binascii.crc32(data)

    def verify_checksum(self):
        return self.calculate_checksum() == int(self['crc'])

    def store_checksum(self):
        self['crc'] = self.calculate_checksum()

class PNGFile(List):
    FILENAME = None
    
    def __init__(self, **kwargs):
        self.filename = kwargs.setdefault('filename', self.FILENAME)
        self.address = kwargs.setdefault('address', self.ADDRESS)

        if not self.filename is None and self.address is None:
            mode = kwargs.setdefault('mode', 'rb')
            self.handle = disk_handle(self.filename, mode)
            self.address = self.handle.address()
            kwargs['address'] = self.address
        else:
            self.handle = None

        super(PNGFile, self).__init__(**kwargs)

        self.declaration.append_declaration(PNGHeader)

        if not self.handle is None:
            self.parse_png()
        else:
            header = self.instantiate(0)
            header.set_value(header.MAGIC)
            header.flush()

    def parse_png(self):
        if self.handle.eof() == 0:
            raise PNGError('png file is empty')
            
        header = self.instantiate(0)
        value = header.get_value()

        if not self.handle.eof() == 0 and not value == header.MAGIC:
            raise PNGError('file is not a valid PNG file, got %X' % value)

        while 1:
            self.declaration.append_declaration(PNGChunk)
            chunk = self.instantiate(-1)

            print 'chunk address', hex(int(chunk.address))
            print 'length', chunk['length'].get_value()
            print 'chunk type', chunk['chunk_type'].get_value()
            print 'chunk size', self.declarations[-1].size().byte_length()
            print 'chunk crc', hex(int(chunk['crc'])), hex(int(chunk['crc'].address))
            print 'data size', chunk['chunk_data'].declaration.size().byte_length()
            print 'chunk info', chunk['chunk_data'].declaration.events

            raw_input()

            if not chunk.verify_checksum():
                raise PNGError('chunk failed checksum, got %X instead of %X' % (chunk.calculate_checksum(), int(chunk['crc'])))

            if chunk['chunk_type'].get_value() == 'IEND':
                break

    def __del__(self):
        self.handle.close(True)
        
file_data = PNGFile(filename='data.png')
