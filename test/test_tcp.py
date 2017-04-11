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

TCPHeader = Structure.subclass(maximum_size=60*8, fields=[
    ('source_port', Word)
    ,('dest_port', Word)
    ,('seq_number', Dword)
    ,('ack_number', Dword)
    ,('data_offset', TCPSizeHint.declare(bitspan=4
                                         ,field_name='options'
                                         ,action=TCPSizeHint.resolve_tcp))
    ,('reserved', Bitfield.declare(bitspan=3))
    ,('flags', Structure.declare(alignment=TCPFlag.ALIGN_BIT, fields=[
        ('ns', TCPFlag)
        ,('cwr', TCPFlag)
        ,('ece', TCPFlag)
        ,('urg', TCPFlag)
        ,('ack', TCPFlag)
        ,('psh', TCPFlag)
        ,('rst', TCPFlag)
        ,('syn', TCPFlag)
        ,('fin', TCPFlag)]))
    ,('window_size', Word)
    ,('checksum', Word)
    ,('urgent_pointer', Word)
    ,('options', ByteArray)])

header = TCPHeader()
header.hexdump()
header.data_offset.set_value(15)
header.hexdump()
header.data_offset.set_value(5)
header.hexdump()
