#!/usr/bin/env python

import math

from paranoia.base import paranoia_agent
from paranoia.types.bitfield import Bitfield
from paranoia.types.structure import Structure

__all__ = ['FloatError', 'FloatStub', 'FloatStruct', 'Float', 'DoubleStruct', 'Double'
           ,'LongDoubleStruct', 'LongDouble', 'DoubleDoubleStruct', 'DoubleDouble']

class FloatError(paranoia_agent.ParanoiaError):
    pass

class FloatStub(object):
    VALUE = None
    
    def __init__(self, **kwargs):
        value = kwargs.setdefault('value', self.VALUE)

        if not value is None:
            self.set_value(value)

    def set_value(self, value):
        if getattr(self, 'sign', None) is None:
            raise FloatError('float object has no sign object')

        if getattr(self, 'exponent', None) is None:
            raise FloatError('float object has no exponent object')

        if getattr(self, 'fraction', None) is None:
            raise FloatError('float object has no fraction object')

        if not isinstance(value, (float, int)):
            raise FloatError('input value must be a float or an int')

        signage = int(value < 0)
        self.sign.set_value(signage)

        value = math.fabs(value)
        lhs = int(math.floor(value))
        rhs = value - lhs

        if lhs == 0:
            lhs_bin = [0]
        else:
            lhs_bin = list()

            while lhs > 0:
                lhs_bin.append(lhs & 1)
                lhs >>= 1

            lhs_bin.reverse()

        if rhs == 0.0:
            rhs_bin = [0]
        else:
            rhs_bin = list()
            bitspan = self.fraction.bitspan

            for i in range(bitspan):
                rhs *= 2
                base_two = int(math.floor(rhs))

                rhs_bin.append(base_two)
                rhs -= base_two

                if rhs == 0.0:
                    break

        if not 1 in lhs_bin and not 1 in rhs_bin:
            self.exponent.set_value(0)
            self.fraction.set_value(0)
            return

        if 1 in lhs_bin:
            index = lhs_bin.index(1)
            normalize = index
            normalize = (len(lhs_bin) - 1) - normalize

            mantissa = lhs_bin[index+1:] + rhs_bin
        elif 1 in rhs_bin:
            index = rhs_bin.index(1)
            normalize = index + 1
            normalize *= -1

            mantissa = rhs_bin[index+1:]

        mantissa += [0] * (self.fraction.bitspan - len(mantissa))
        exponent = normalize + (2 ** (self.exponent.bitspan - 1) - 1)

        fraction = 0

        for i in range(len(mantissa)):
            fraction <<= 1
            fraction |= mantissa[i]

        self.exponent.set_value(exponent)
        self.fraction.set_value(fraction)
            
    def get_value(self):
        if getattr(self, 'sign', None) is None:
            raise FloatError('float object has no sign object')

        if getattr(self, 'exponent', None) is None:
            raise FloatError('float object has no exponent object')

        if getattr(self, 'fraction', None) is None:
            raise FloatError('float object has no fraction object')

        exponent = int(self.exponent) - (2 ** (self.exponent.bitspan - 1) - 1)
        fraction = int(self.fraction)
        fraction_list = list()

        while not len(fraction_list) == self.fraction.bitspan:
            fraction_list.append(fraction & 1)
            fraction >>= 1

        fraction_list.reverse()
        fraction_list = [1] + fraction_list
        
        result = 0

        for i in range(len(fraction_list)):
            if fraction_list[i] == 0:
                continue

            result += 2 ** (exponent - i)

        if int(self.sign):
            result *= -1

        return result * 1.0

    def __int__(self):
        return int(float(self))

    def __float__(self):
        return self.get_value()    

FloatStruct = Structure.simple([
        ('sign', Bitfield, {'bitspan': 1})
        ,('exponent', Bitfield, {'bitspan': 8})
        ,('fraction', Bitfield, {'bitspan': 23})])

class Float(FloatStruct, FloatStub):
    def __init__(self, **kwargs):
        FloatStruct.__init__(self, **kwargs)
        FloatStub.__init__(self, **kwargs)

DoubleStruct = Structure.simple([
        ('sign', Bitfield, {'bitspan': 1})
        ,('exponent', Bitfield, {'bitspan': 11})
        ,('fraction', Bitfield, {'bitspan': 52})])

class Double(DoubleStruct, FloatStub):
    def __init__(self, **kwargs):
        DoubleStruct.__init__(self, **kwargs)
        FloatStub.__init__(self, **kwargs)

LongDoubleStruct = Structure.simple([
        ('sign', Bitfield, {'bitspan': 1})
        ,('exponent', Bitfield, {'bitspan': 15})
        ,('fraction', Bitfield, {'bitspan': 63})])

class LongDouble(LongDoubleStruct, FloatStub):
    def __init__(self, **kwargs):
        LongDoubleStruct.__init__(self, **kwargs)
        FloatStub.__init__(self, **kwargs)

DoubleDoubleStruct = Structure.simple([
        ('sign', Bitfield, {'bitspan': 1})
        ,('exponent', Bitfield, {'bitspan': 15})
        ,('fraction', Bitfield, {'bitspan': 112})])

class DoubleDouble(DoubleDoubleStruct, FloatStub):
    def __init__(self, **kwargs):
        DoubleDoubleStruct.__init__(self, **kwargs)
        FloatStub.__init__(self, **kwargs)
