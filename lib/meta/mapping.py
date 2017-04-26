#!/usr/bin/env python

import copy
import inspect

from paranoia.meta.declaration import Declaration
from paranoia.meta.list import List, ListError
from paranoia.meta.region import Region

__all__ = ['MappingError', 'Mapping']

class MappingError(ListError):
    pass

class Mapping(List):
    FIELDS = None

    def __init__(self, **kwargs):
        self.declaration = kwargs.setdefault('declaration', self.DECLARATION)

        if self.declaration is None:
            self.declaration = declaration.Declaration(base_class=self.__class__, args=kwargs)
            
        self.declaration = memory_region.ensure_declaration(self.declaration)
        self.field_map, self.anon_map, self.declarations = self.parse_fields(self.declaration)
        kwargs['declarations'] = self.declarations
        
        super(Mapping, self).__init__(**kwargs)

    def parse_fields(self, decl):
        if not isinstance(decl, declaration.Declaration):
            raise MappingError('decl must be a Declaration object')
        
        fields = decl.args.get('fields', None)

        if fields is None and not decl.base_class.FIELDS is None:
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
            field_decl = memory_region.ensure_declaration(field_decl)
            field_pair[1] = field_decl

            if fieldname in field_map:
                raise MappingError('field name already in field map')

            if fieldname is None:
                fieldname = '__anon_field_%X' % id(field_decl)
                sub_anon_map = self.parse_anonymous_field(field_decl)

                for anon_field in sub_anon_map:
                    if anon_field in field_map or anon_field in anon_map:
                        raise MappingError('either anonymously named mapping or another field is already taking up the name %s' % anon_name)

                    anon_map[anon_field] = sub_anon_map[anon_field]

            declarations.append(field_decl)
            field_map[fieldname] = id(field_decl)

        decl.set_arg('fields', fields)
        return (field_map, anon_map, declarations)

    def parse_anonymous_field(self, decl):
        if not isinstance(decl, declaration.Declaration):
            raise MappingError('decl must be a Declaration object')
        
        anon_map = dict()
        
        if not issubclass(decl.base_class, Mapping):
            raise MappingError('only mapping objects can have anonymous fields')

        anon_field_map, anon_anon_map, anon_decls = self.parse_fields(decl)
                
        for anon_field in anon_field_map:
            if anon_field in anon_map:
                raise MappingError('anon field name already in anon map')
            
            anon_map[anon_field] = id(decl)

        for anon_field in anon_anon_map:
            if anon_field in anon_map:
                raise MappingError('anon field name already in anon map')

            anon_map[anon_field] = id(decl)

        return anon_map

    def get_field_declaration(self, field):
        if field in self.field_map:
            decl_id = self.field_map[field]
        else:
            raise AttributeError(field)

        if not decl_id in self.declaration_index:
            raise AttributeError(field)
            
        offset = self.declaration_index[decl_id]
        return (offset, self.declarations[offset])

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

    @classmethod
    def static_bitspan(cls, **kwargs):
        fields = kwargs.setdefault('fields', cls.FIELDS)
        decls = map(lambda x: memory_region.ensure_declaration(x[1]), fields)
        overlaps = kwargs.setdefault('overlaps', cls.OVERLAPS)
        
        return cls.declarative_size(overlaps, decls)

    @classmethod
    def subclass(cls, **kwargs):
        kwargs.setdefault('fields', cls.FIELDS)

        super_class = super(Mapping, cls).subclass(**kwargs)

        class SubclassedMapping(super_class):
            FIELDS = kwargs['fields']

        return SubclassedMapping
