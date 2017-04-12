#!/usr/bin/env python

from paranoia.types import *
from paranoia.meta.size_hint import SizeHint

class TCPSizeHint(SizeHint):
    ALIGNMENT = SizeHint.ALIGN_BIT

    def resolve_tcp(self, decl):
        value = self.get_value()

        if value < 5:
            value = 0
        else:
            value -= 5
            value *= 4

        if decl.instance is None:
            decl.set_arg('elements', value)
        else:
            decl.instance.set_elements(value)

TCPFlag = Bitfield.subclass(bitspan=1)

TCPHeader = Structure.subclass(maximum_size=60*8, fields=
    [('source_port', Word.declare(endianness=Word.BIG_ENDIAN))
    ,('dest_port', Word.declare(endianness=Word.BIG_ENDIAN))
    ,('seq_number', Dword.declare(endianness=Dword.BIG_ENDIAN))
    ,('ack_number', Dword.declare(endianness=Dword.BIG_ENDIAN))
    ,('data_offset', TCPSizeHint.declare(bitspan=4
                                         ,field_name='options'
                                         ,action=TCPSizeHint.resolve_tcp))
    ,('reserved', Bitfield.declare(bitspan=3))
    ,('flags', Structure.declare(alignment=TCPFlag.ALIGN_BIT, fields=
        [('ns', TCPFlag)
        ,('cwr', TCPFlag)
        ,('ece', TCPFlag)
        ,('urg', TCPFlag)
        ,('ack', TCPFlag)
        ,('psh', TCPFlag)
        ,('rst', TCPFlag)
        ,('syn', TCPFlag)
        ,('fin', TCPFlag)]))
    ,('window_size', Word.declare(endianness=Word.BIG_ENDIAN))
    ,('checksum', Word.declare(endianness=Word.BIG_ENDIAN))
    ,('urgent_pointer', Word.declare(endianness=Word.BIG_ENDIAN))
    ,('options', ByteArray)])

header = TCPHeader()
header.hexdump()
header.data_offset.set_value(15)
header.hexdump()
header.data_offset.set_value(5)
header.hexdump()

real_header = TCPHeader(data='\x1e\xb7\01\xbb\x00\xa7\x8a\x47\x00\x00\x00\x00\x80\x02\x20\x00\xba\x27\x00\x00\x02\x04\x05\xb4\x01\x03\x03\x08\x01\x01\x04\x02')

real_header.hexdump()
