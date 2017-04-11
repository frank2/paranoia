#!/usr/bin/env python

from paranoia.base import numeric_region

__all__ = ['SizeHintError', 'SizeHint']

class SizeHintError(numeric_region.NumericRegionError):
    pass

class SizeHint(numeric_region.NumericRegion):
    DECLARATION_OFFSET = None
    DECLARATION_ID = None
    FIELD_NAME = None
    ACTION = None

    def __init__(self, **kwargs):
        numeric_region.NumericRegion.__init__(self, **kwargs)
        self.init_finished = False
        
        declaration_offset = kwargs.setdefault('declaration_offset', self.DECLARATION_OFFSET)
        field_name = kwargs.setdefault('field_name', self.FIELD_NAME)
        self.declaration_id = kwargs.setdefault('declaration_id', self.DECLARATION_ID)
        self.action = kwargs.setdefault('action', self.ACTION)

        if declaration_offset is None and field_name is None and self.declaration_id is None:
            raise SizeHintError('size hint must point at a declaration offset, a field name or a declaration ID')
        elif not field_name is None:
            self.set_field_name(field_name)
        elif not declaration_offset is None:
            self.set_offset(declaration_offset)

        self.init_finished = True

    def set_id(self, decl_id):
        self.declaration_id = decl_id

        if self.init_finished:
            self.resolve()

    def set_offset(self, offset):
        self.set_id(id(self.parent_region.declarations[offset]))

    def set_field_name(self, field_name):
        self.set_id(self.parent_region.field_map[field_name])

    def set_value(self, value):
        super(SizeHint, self).set_value(value)
        self.resolve()

    def resolve(self):
        decl = None

        for d in self.parent_region.declarations:
            if id(d) == self.declaration_id:
                decl = d
                break

        if decl is None:
            raise SizeHintError('declaration not found')

        value = self.get_value()

        if self.action == 'resize' or self.action is None:
            if decl.instance is None:
                decl.set_arg('bitspan', value)
            else:
                decl.instance.resize(value)
        elif self.action == 'set_elements':
            if decl.instance is None:
                decl.set_arg('elements', value)
            else:
                decl.instance.set_elements(value)
        elif isinstance(self.action, str):
            if decl.instance is None:
                decl.set_arg(self.action, value)
            else:
                setattr(decl.instance, self.action, value)
        elif callable(self.action):
            self.action(self, decl)
        else:
            raise SizeHintError('incompatible action')

    @staticmethod
    def find_target(hint_decl, list_obj, declarations):
        offset_arg = hint_decl.args.get('offset', None)

        if not offset_arg is None:
            return offset_arg

        field_arg = hint_decl.args.get('field_name', None)

        if field_arg is None:
            id_arg = hint_decl.args.get('declaration_id', None)
        else:
            id_arg = list_obj.field_map[field_arg]

        if not id_arg is None:
            for i in xrange(len(declarations)):
                decl = declarations[i]
                
                if id(decl) == id_arg:
                    return i

        raise SizeHintError('could not find declaration')
