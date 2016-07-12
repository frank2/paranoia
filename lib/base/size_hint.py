#!/usr/bin/env python

from paranoia.base import numeric_region

class SizeHintError(numeric_region.NumericRegionError):
    pass

class SizeHint(numeric_region.NumericRegion):
    MY_DECLARATION = None
    TARGET_DECLARATION = None
    ARGUMENT = 'bitspan'

    def __init__(self, **kwargs):
        self.my_declaration = kwargs.setdefault('my_declaration', self.MY_DECLARATION)
        self.target_declaration = kwargs.setdefault('target_declaration', self.TARGET_DECLARATION)
        self.argument = kwargs.setdefault('argument', self.ARGUMENT)

        if self.my_declaration is None:
            raise SizeHintError('my_declaration not set')

        if self.target_declaration is None:
            raise SizeHintError('target_declaration not set')

        if self.argument is None:
            raise SizeHintError('argument not set')

        if not isinstance(self.my_declaration, (int, long)):
            raise SizeHintError('my_declaration must be an int or long')

        if not isinstance(self.target_declaration, (int, long, basestring)):
            raise SizeHintError('size_offset not an int, long or string')

        if not isinstance(self.argument, basestring):
            raise SizeHintError('argument not a string')

        numeric_region.NumericRegion.__init__(self, **kwargs)

    def set_declaration(self):
        declarations = getattr(self.parent_region, 'declarations', None)

        if not declarations:
            raise SizeHintError('parent_region has no declarations')

        print '[set_declaration]', self.target_declaration, self.argument, self.get_value()
        declarations[self.target_declaration].args[self.argument] = self.get_value()

    def set_value(self, value):
        numeric_region.NumericRegion.set_value(self, value)
        
        self.set_declaration()
