#!/usr/bin/env python

from paranoia.base.size import Size
from paranoia.meta.declaration import Declaration
from paranoia.meta.region import NumericRegion, RegionError, RegionDeclaration, RegionDeclarationError
from paranoia.fundamentals import dict_merge

__all__ = ['SizeHintError', 'SizeHint']

class SizeHintError(RegionError):
    pass

class SizeHintDeclarationError(RegionDeclarationError):
    pass

class SizeHintDeclaration(RegionDeclaration):
    def __init__(self, **kwargs):
        super(SizeHintDeclaration, self).__init__(**kwargs)

        if self.get_arg('declaration_offset') is None and self.get_arg('field_name') is None:
            raise SizeHintDeclarationError('both declaration_offset and field_name cannot be None')
        
    def resolve(self, **kwargs):
        from paranoia.meta.array import ArrayDeclaration
        from paranoia.meta.mapping import MappingDeclaration
        from paranoia.meta.list import ListDeclaration

        dict_merge(kwargs, self.args)

        field_name = kwargs.get('field_name')
        declaration_offset = kwargs.get('declaration_offset')
        action = kwargs.get('action')
        parent_declaration = kwargs.get('parent_declaration')

        if parent_declaration is None:
            raise SizeHintError('cannot resolve size hint without a parent declaration')

        if field_name is None and declaration_offset is None:
            raise SizeHintError('no field name or declaration offset given')

        target_decl = None

        if not field_name is None:
            if not isinstance(parent_declaration, MappingDeclaration):
                raise SizeHintError('parent declaration not a MappingDeclaration')
            
            decl = parent_declaration.get_field(field_name)
        elif not declaration_offset is None:
            if not isinstance(parent_declaration, ListDeclaration):
                raise SizeHintError('parent declaration not a ListDeclaration')
            
            decl = parent_declaration.get_arg('declarations')[declaration_offset]
            
        value = self.get_value(**kwargs)

        if action == 'bytes' or action is None:
            new_size = Size(bytes=value)
            decl.set_size(new_size)
        elif action == 'bits':
            new_size = Size(bits=value)
            decl.set_size(new_size)
        elif action == 'set_elements':
            if not isinstance(decl, ArrayDeclaration):
                raise SizeHintError('declaration not an ArrayDeclaration')
            
            decl.set_elements(value)
        elif isinstance(action, str):
            decl.set_arg(action, value)
        elif callable(action):
            action(self, decl, value)
        else:
            raise SizeHintError('incompatible action')

class SizeHint(NumericRegion):
    DECLARATION_CLASS = SizeHintDeclaration
    DECLARATION_OFFSET = None
    FIELD_NAME = None
    ACTION = None

    def __init__(self, **kwargs):
        self.declaration_offset = kwargs.setdefault('declaration_offset', self.DECLARATION_OFFSET)
        self.field_name = kwargs.setdefault('field_name', self.FIELD_NAME)
        self.action = kwargs.setdefault('action', self.ACTION)
        
        super(SizeHint, self).__init__(**kwargs)

    def set_offset(self, offset):
        self.declaration.set_offset(offset)

    def set_field_name(self, field_name):
        self.declaration.set_field_name(field_name)

    def set_value(self, value):
        super(SizeHint, self).set_value(value)

        if self.init_finished:
            self.resolve()

    def resolve(self, **kwargs):
        self.declaration.resolve(**kwargs)

SizeHintDeclaration.BASE_CLASS = SizeHint
