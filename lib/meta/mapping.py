#!/usr/bin/env python

import copy
import inspect

from paranoia.meta.declaration import Declaration, ensure_declaration
from paranoia.meta.list import ListDeclaration, ListDeclarationError, List, ListError
from paranoia.meta.region import Region

__all__ = ['MappingDeclarationError', 'MappingDeclaration', 'MappingError', 'Mapping']

class MappingDeclarationError(ListError):
    pass

class MappingDeclaration(ListDeclaration):
    def __init__(self, **kwargs):
        super(MappingDeclaration, self).__init__(**kwargs)

        fields = self.get_arg('fields')

        if fields is None:
            fields = self.base_class.FIELDS

        if fields is None:
            fields = list()

        self.parse_fields(fields)

    def get_field_offset(self, field):
        field_map = self.get_arg('field_map')

        if field_map is None:
            raise MappingDeclarationError('no field map present')

        anon_map = self.get_arg('anon_map')

        if anon_map is None:
            raise MappingDeclarationError('no anon map present')
        
        if field in field_map:
            decl_id = field_map[field]
        elif field in anon_map:
            decl_id = anon_map[field]
        else:
            raise MappingDeclarationError('no such field %s in field map' % field)

        if not decl_id in self.declaration_index:
            raise MappingDeclarationError('declaration not in list')
            
        return self.declaration_index[decl_id]

    def get_field(self, field):
        field_map = self.get_arg('field_map')

        if field_map is None:
            raise MappingDeclarationError('no field map present')

        anon_map = self.get_arg('anon_map')

        if anon_map is None:
            raise MappingDeclarationError('no anon map present')

        decl = self

        while field in anon_map:
            offset = decl.get_field_offset(field)
            declarations = decl.get_arg('declarations')
            decl = declarations[offset]
            field_map = decl.get_arg('field_map')
            anon_map = decl.get_arg('anon_map')

        declarations = decl.get_arg('declarations')

        if field in field_map:
            return declarations[self.get_field_offset(field)]
        else:
            raise MappingDeclarationError('field not found')

    def parse_fields(self, fields):
        if not isinstance(fields, (list, tuple)):
            raise MappingDeclarationError('fields must be a list/tuple containing field names and declarations')

        if fields == self.base_class.FIELDS:
            fields = map(lambda x: [x[0], copy.deepcopy(x[1])], fields)

        # we need to modify the fields, change this
        if isinstance(fields, tuple):
            fields = list(fields)

        if fields is None or not isinstance(fields, list):
            raise MappingDeclarationError('fields must be pairs of names and Declaration or MemoryRegion types')

        field_map = dict()
        anon_map = dict()
        declarations = list()

        for field_index in xrange(len(fields)):
            field_pair = fields[field_index]

            if not len(field_pair) == 2:
                raise MappingDeclarationError('field_pair must be a pair of name and Declaration or MemoryRegion')

            if isinstance(field_pair, tuple):
                # needs to be modified, fix it
                fields[field_index] = list(field_pair)
                field_pair = fields[field_index]

            fieldname, field_decl = field_pair
            field_decl = ensure_declaration(field_decl)
            field_pair[1] = field_decl

            if fieldname in field_map:
                raise MappingError('field name already in field map')

            if fieldname is None:
                fieldname = '__anon_field_%X' % id(field_decl)
                sub_anon_map = self.parse_anonymous_field(field_decl)

                for anon_field in sub_anon_map:
                    if anon_field in field_map or anon_field in anon_map:
                        raise MappingDeclarationError('either anonymously named mapping or another field is already taking up the name %s' % anon_name)

                    anon_map[anon_field] = sub_anon_map[anon_field]

            declarations.append(field_decl)
            field_map[fieldname] = id(field_decl)

        self.set_arg('fields', fields)
        self.set_arg('field_map', field_map)
        self.set_arg('anon_map', anon_map)
        self.set_arg('declarations', declarations)
        
        self.map_declarations()

    def parse_anonymous_field(self, anon_decl):
        if not isinstance(anon_decl, MappingDeclaration):
            raise MappingDeclarationError('decl must be a MappingDeclaration object')
        
        anon_map = dict()
        anon_field_map = anon_decl.get_arg('field_map')
        anon_anon_map = anon_decl.get_arg('anon_map')
                
        for anon_field in anon_field_map:
            if anon_field in anon_map:
                raise MappingDeclarationError('anon field name already in anon map')
            
            anon_map[anon_field] = id(anon_decl)

        for anon_field in anon_anon_map:
            if anon_field in anon_map:
                raise MappingDeclarationError('anon field name already in anon map')

            anon_map[anon_field] = id(anon_decl)

        return anon_map

    def instantiate(self, **kwargs):
        field_map = self.get_arg('field_map')
        anon_map = self.get_arg('anon_map')
        instance = super(MappingDeclaration, self).instantiate(**kwargs)
        instance.field_map = field_map
        instance.anon_map = anon_map
        
        return instance

class MappingError(ListError):
    pass

class Mapping(List):
    DECLARATION_CLASS = MappingDeclaration
    FIELDS = None

    def __init__(self, **kwargs):
        self.fields = kwargs.setdefault('fields', self.FIELDS)
        
        super(Mapping, self).__init__(**kwargs)

    def get_field(self, key):
        if isinstance(key, int):
            return self.instantiate(key)
        elif not isinstance(key, str):
            raise MappingError('key must be an int or a string')

        offset = self.declaration.get_field_offset(key)
        field_map = self.field_map

        if key in field_map:
            return self.instantiate(offset)

        anon_map = self.anon_map
        mapping = self
        
        while key in anon_map:
            offset = mapping.declaration.get_field_offset(key)
            mapping = mapping.instantiate(offset)
            field_map = mapping.field_map
            anon_map = mapping.anon_map

        if not key in field_map:
            raise MappingError('field %s not found' % key)

        offset = mapping.declaration.get_field_offset(key)
        return mapping.instantiate(offset)

    def __getitem__(self, key):
        return self.get_field(key)

    def __setitem__(self, key, value):
        self.get_field(key).set_value(value)

    def __contains__(self, key):
        return key in self.field_map or key in self.anon_map

    def __iter__(self):
        for field in self.field_map:
            yield field

        for field in self.anon_map:
            yield field

    @classmethod
    def static_size(cls, **kwargs):
        fields = kwargs.setdefault('fields', cls.FIELDS)
        kwargs['declarations'] = map(lambda x: ensure_declaration(x[1]), fields)
        return super(Mapping, cls).static_size(**kwargs)

    @classmethod
    def bit_parser(cls, **kwargs):
        fields = kwargs.setdefault('fields', cls.FIELDS)
        kwargs['declarations'] = map(lambda x: ensure_declaration(x[1]), fields)
        return super(Mapping, cls).bit_parser(**kwargs)

    @classmethod
    def subclass(cls, **kwargs):
        kwargs.setdefault('fields', cls.FIELDS)

        super_class = super(Mapping, cls).subclass(**kwargs)

        class SubclassedMapping(super_class):
            FIELDS = kwargs['fields']

        return SubclassedMapping

    @classmethod
    def declare(cls, **kwargs):
        kwargs.setdefault('fields', cls.FIELDS)

        super_decl = super(Mapping, cls).declare(**kwargs)
        super_decl.base_class = cls
 
        return super_decl

MappingDeclaration.BASE_CLASS = Mapping
