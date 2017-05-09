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
        args = kwargs.setdefault('args', dict())

        fields = kwargs.get('fields')

        if fields is None:
            fields = list()

        field_map, anon_map, declarations = self.parse_fields(fields)

        args['field_map'] = field_map
        args['anon_map'] = anon_map
        args['declarations'] = declarations

        super(MappingDeclaration, self).__init__(**kwargs)

        self.set_arg('field_map', field_map)
        self.set_arg('anon_map', anon_map)

    def get_field_offset(self, field):
        if field in self.field_map:
            decl_id = self.field_map[field]
        else:
            raise MappingDeclarationError('no such field %s in field map' % field)

        if not decl_id in self.declaration_index:
            raise MappingDeclarationError('declaration not in list')
            
        return self.declaration_index[decl_id]

    def get_field(self, field):
        declarations = self.get_arg('declarations')
        field_map = self.get_arg('field_map')
        anon_map = self.get_arg('anon_map')

        return declarations[self.get_field_offset(field)]

class MappingError(ListError):
    pass

class Mapping(List):
    DECLARATION_CLASS = MappingDeclaration
    FIELDS = None

    def __init__(self, **kwargs):
        self.fields = kwargs.setdefault('fields', self.FIELDS)
        
        super(Mapping, self).__init__(**kwargs)

    def get_field(self, field):
        if field in self.field_map:
            offset, decl = self.get_field_declaration(field)
            return self.instantiate(offset)
        elif not field in self.anon_map:
            raise AttributeError(field)

        anon_id = self.anon_map[field]

        if not anon_id in self.declaration_index:
            raise AttributeError(field)

        offset = self.declaration_index[anon_id]

        return self.instantiate(offset).get_field(field)

    def __getattr__(self, attr):
        if 'field_map' not in self.__dict__ and 'anon_map' not in self.__dict__ and attr not in self.__dict__:
            raise AttributeError(attr)

        field_map = self.__dict__['field_map']
        anon_map = self.__dict__['anon_map']

        if attr in field_map or attr in anon_map:
            return self.get_field(attr)
        if attr in self.__dict__:
            return self.__dict__[attr]
        else:
            raise AttributeError(attr)

    @staticmethod
    def parse_fields(decl):
        if not isinstance(decl, Declaration):
            raise MappingError('decl must be a Declaration object')

        if not issubclass(decl.base_class, Mapping):
            raise MappingError('declaration is not a Mapping declaration')
        
        fields = decl.get_arg('fields')

        if fields == decl.base_class.FIELDS:
            fields = map(lambda x: [x[0], copy.deepcopy(x[1])], decl.base_class.FIELDS)

        # we need to modify the fields, change this
        if isinstance(fields, tuple):
            fields = list(fields)

        if fields is None or not isinstance(fields, list):
            raise MappingError('fields must be pairs of names and Declaration or MemoryRegion types')

        field_map = dict()
        anon_map = dict()
        declarations = list()

        for field_index in xrange(len(fields)):
            field_pair = fields[field_index]

            if not len(field_pair) == 2:
                raise MappingError('field_pair must be a pair of name and Declaration or MemoryRegion')

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
                sub_anon_map = Mapping.parse_anonymous_field(field_decl)

                for anon_field in sub_anon_map:
                    if anon_field in field_map or anon_field in anon_map:
                        raise MappingError('either anonymously named mapping or another field is already taking up the name %s' % anon_name)

                    anon_map[anon_field] = sub_anon_map[anon_field]

            declarations.append(field_decl)
            field_map[fieldname] = id(field_decl)

        decl.set_arg('fields', fields)
        return (field_map, anon_map, declarations)

    @staticmethod
    def parse_anonymous_field(decl):
        if not isinstance(decl, Declaration):
            raise MappingError('decl must be a Declaration object')
        
        anon_map = dict()
        
        if not issubclass(decl.base_class, Mapping):
            raise MappingError('only mapping objects can have anonymous fields')

        anon_field_map, anon_anon_map, anon_decls = Mapping.parse_fields(decl)
                
        for anon_field in anon_field_map:
            if anon_field in anon_map:
                raise MappingError('anon field name already in anon map')
            
            anon_map[anon_field] = id(decl)

        for anon_field in anon_anon_map:
            if anon_field in anon_map:
                raise MappingError('anon field name already in anon map')

            anon_map[anon_field] = id(decl)

        return anon_map

    @classmethod
    def static_size(cls, **kwargs):
        fields = kwargs.setdefault('fields', cls.FIELDS)
        kwargs['declarations'] = map(lambda x: ensure_declaration(x[1]), fields)
        result = super(Mapping, cls).static_size(**kwargs)
        return result

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
