#!/usr/bin/env python

from paranoia.base import numeric_region

class SizeHintError(numeric_region.NumericRegionError):
    pass

class SizeHint(numeric_region.NumericRegion):
    TARGET_DECLARATION = None
    RESOLVED_DECLARATION = None
    ARGUMENT = 'bitspan'

    def __init__(self, **kwargs):
        self.target_declaration = kwargs.setdefault('target_declaration', self.TARGET_DECLARATION)
        self.resolved_declaration = kwargs.setdefault('resolved_declaration', self.RESOLVED_DECLARATION)
        self.argument = kwargs.setdefault('argument', self.ARGUMENT)

        if self.target_declaration is None:
            raise SizeHintError('target_declaration not set')

        if self.argument is None:
            raise SizeHintError('argument not set')

        if not isinstance(self.target_declaration, (int, long, basestring)):
            raise SizeHintError('target_declaration not an int, long or string')

        if not self.resolved_declaration is None and not isinstance(self.resolved_declaration, (int, long)):
            raise SizeHintError('resolved_declaration must be a hash of a declaration')

        if not isinstance(self.argument, basestring):
            raise SizeHintError('argument not a string')

        numeric_region.NumericRegion.__init__(self, **kwargs)

    def set_declaration(self):
        if not self.resolved_declaration is None:
            declaration_map = getattr(self.parent_region, 'declaration_map', None)

            if not declaration_map:
                raise SizeHintError('parent_region has no declaration map')

            if not declaration_map.has_key(self.resolved_declaration):
                raise SizeHintError('no declaration found with hash 0x%x' % self.resolved_declaration)
        
            declaration_map[self.resolved_declaration].set_arg(self.argument, self.get_value())
        else:
            declarations = getattr(self.parent_region, 'declarations', None)

            if not declarations:
                raise SizeHintError('parent_region has no declarations')

            if self.target_declaration >= len(declarations):
                raise SizeHintError('target declaration out of bounds')
        
            declarations[self.target_declaration].set_arg(self.argument, self.get_value())


    def set_value(self, value):
        numeric_region.NumericRegion.set_value(self, value)
        
        self.set_declaration()

        recalculate = getattr(self.parent_region, 'recalculate', None)

        if recalculate:
            recalculate(self.declaration)

    def resolve(self, resolution=None):
        if isinstance(self.target_declaration, basestring):
            if resolution is None:
                raise SizeHintError('cannot resolve string without resolution')

            self.resolved_declaration = resolution
            return

        declarations = getattr(self.parent_region, 'declarations', None)

        if declarations is None:
            raise SizeHintError('parent_region has no declarations')

        if self.target_declaration >= len(declarations):
            raise SizeHintError('target declaration out of bounds')
        
        self.resolved_declaration = hash(declarations[self.target_declaration])
