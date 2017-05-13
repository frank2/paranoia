#!/usr/bin/env python

import cProfile

from paranoia.types import *
from paranoia.base.size import Size
from paranoia.meta.size_hint import SizeHint, SizeHintDeclaration

class TCPSizeHint(SizeHint):
    ALIGNMENT = SizeHint.ALIGN_BIT

    @staticmethod
    def resolve_hint(size_decl, target_decl, value):
        if value < 5:
            value = 0
        else:
            value -= 5
            value *= 4

        target_decl.set_elements(value)

def test():
    TCPFlag = Bitfield.subclass(size=Size(bits=1))

    TCPHeader = Structure.subclass(maximum_size=Size(bytes=60), fields=
    [('source_port', Word.declare(endianness=Word.BIG_ENDIAN))
    ,('dest_port', Word.declare(endianness=Word.BIG_ENDIAN))
    ,('seq_number', Dword.declare(endianness=Dword.BIG_ENDIAN))
    ,('ack_number', Dword.declare(endianness=Dword.BIG_ENDIAN))
    ,('data_offset', TCPSizeHint.declare(size=Size(bits=4)
                                         ,field_name='options'
                                         ,action=TCPSizeHint.resolve_hint))
    ,('reserved', Bitfield.declare(size=Size(bits=3)))
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
    header['data_offset'].set_value(15)
    header['data_offset'].flush()
    header.hexdump()
    header['data_offset'].set_value(5)
    header['data_offset'].flush()
    header.hexdump()

    real_header = TCPHeader(block_data='\x1e\xb7\01\xbb\x00\xa7\x8a\x47\x00\x00\x00\x00\x80\x02\x20\x00\xba\x27\x00\x00\x02\x04\x05\xb4\x01\x03\x03\x08\x01\x01\x04\x02')
    real_header.hexdump()

cProfile.run('test()', sort='cumtime')
