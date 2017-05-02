#!/usr/bin/env python

from paranoia.base.size import Size
from paranoia.meta.declaration import Declaration
from paranoia.meta.region import NumericRegion, RegionError
from paranoia.fundamentals import dict_merge

__all__ = ['SizeHintError', 'SizeHint']

class SizeHintError(RegionError):
    pass

class SizeHint(NumericRegion):
    DECLARATION_OFFSET = None
    FIELD_NAME = None
    ACTION = None

    def __init__(self, **kwargs):
        super(SizeHint, self).__init__(**kwargs)
        
        self.init_finished = False
        
        self.declaration_id = None
        declaration_offset = kwargs.setdefault('declaration_offset', self.DECLARATION_OFFSET)
        field_name = kwargs.setdefault('field_name', self.FIELD_NAME)
        self.action = kwargs.setdefault('action', self.ACTION)

        if declaration_offset is None and field_name is None:
            raise SizeHintError('size hint must point at a declaration offset or a field name')
        elif not field_name is None:
            self.set_field_name(field_name)
        elif not declaration_offset is None:
            self.set_offset(declaration_offset)

        self.init_finished = True

    def set_offset(self, offset):
        self.declaration_offset = offset
        self.field_name = None

        if self.init_finished:
            self.resolve()

    def set_field_name(self, field_name):
        self.field_name = field_name
        self.declaration_offset = None

        if self.init_finished:
            self.resolve()

    def set_value(self, value):
        super(SizeHint, self).set_value(value)

        if self.init_finished:
            self.resolve()

    def resolve(self):
        args = {'declaration': self.declaration}
        dict_merge(args, self.declaration.args)
        
        self.static_resolution(**args)

    @classmethod
    def static_resolution(cls, **kwargs):
        from paranoia.meta.mapping import Mapping
        from paranoia.meta.list import List
        
        parent_declaration = kwargs.setdefault('parent_declaration', None)
        declaration = kwargs.setdefault('declaration', cls.DECLARATION)
        field_name = kwargs.setdefault('field_name', cls.FIELD_NAME)
        declaration_offset = kwargs.setdefault('declaration_offset', cls.DECLARATION_OFFSET)
        action = kwargs.setdefault('action', cls.ACTION)

        if declaration is None:
            declaration = Declaration(base_class=cls, args=kwargs)

        if parent_declaration is None:
            raise SizeHintError('cannot resolve size hint without a parent declaration')

        if field_name is None and declaration_offset is None:
            raise SizeHintError('no field name or declaration offset given')

        target_decl = None

        if not field_name is None:
            field_map, anon_map, declarations = Mapping.parse_fields(parent_declaration)
            declaration_map = dict(map(lambda x: (id(x), x), declarations))

            if field_name in field_map:
                decl = declaration_map[field_map[field_name]]
            elif field_name in anon_map:
                while not field_name in field_map and field_name in anon_map:
                    anon_decl = declaration_map[anon_map[field_name]]
                    field_map, anon_map, declarations = Mapping.parse_fields(anon_decl)
                    declaration_map = dict(map(lambda x: (id(x), x), declarations))

                decl = declaration_map[field_map[field_name]]
        elif not declaration_offset is None:
            decl = parent_declaration.get_arg('declarations')[declaration_offset]

        if not declaration.instance is None:
            value = declaration.instance.get_value()
        else:
            value = NumericRegion.static_value(**kwargs)

        if action == 'bytes' or action is None:
            new_size = Size(bytes=value)
            decl.set_size(new_size)
        elif action == 'bits':
            new_size = Size(bits=value)
            decl.set_size(new_size)
        elif action == 'set_elements':
            decl.set_elements(value)
        elif isinstance(action, str):
            decl.set_arg(action, value)
        elif callable(action):
            action(declaration, decl)
        else:
            raise SizeHintError('incompatible action')

