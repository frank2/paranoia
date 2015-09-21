#!/usr/bin/env python

from . import list as d_list
from . import declaration
from .. import memory_region

class MappingError(d_list.ListError):
    pass

class Mapping(d_list.List):
    FIELDS = None

    def __init__(self, **kwargs):
        fields = kwargs.setdefault('fields', self.FIELDS)

        if fields is None or not getattr(fields, '__iter__', None):
            raise StructureError('fields must be a sequence of names and DataDeclarations')

        self.parse_fields(fields)
        kwargs['declarations'] = self.declarations # for initializing bitspan

        d_list.List.__init__(self, **kwargs)

    def parse_fields(self, fields):
        self.declarations = list()
        self.field_map = dict()
        self.anon_map = dict()
        anonymous_fields = 0

        for pair in fields:
            if not len(pair) == 2 or not isinstance(pair[0], basestring) or not isinstance(struct_pair[1], declaration.Declaration):
                raise MappingError('field_declaration element must be a pair consisting of a string or None paired with a Declaration.')
            
            name, declaration_obj = struct_pair

            if name == None:
                if not issubclass(declaration_obj.base_class, Mapping):
                    raise MappingError('only Mapping types can be anonymously named')
                
                name = '__anon_field%04d' % anonymous_fields
                anonymous_fields += 1
                found_fields = declaration_obj.args.get('fields', None) or declaration_obj.BASE_CLASS.FIELDS

                if not found_fields:
                    raise MappingError('no fields in declaration object')

                for anon_field in found_fields:
                    anon_name, anon_decl = anon_field

                    if self.anon_map.has_key(anon_name) or self.field_map.has_key(anon_name):
                        raise MappingError('either another anonymously named mapping or another field is already taking up the name %s' % anon_name)

                    self.anon_map[anon_name] = name
                
            index = len(self.declarations)
            self.declarations.append(declaration_obj)
            
            if self.field_map.has_key(name):
                raise StructureError('%s already defined in structure' % name)

            self.field_map[name] = index

    def __getattr__(self, attr):
        if not self.__dict__.has_key('field_map') and not self.__dict__.has_key(attr):
            raise AttributeError(attr)
        elif not self.__dict__.has_key('field_map'):
            return self.__dict__[attr]

        field_map = self.__dict__['field_map']

        if field_map.has_key(attr):
            index = field_map[attr]
            return self.instantiate(index)
        else:
            raise AttributeError(attr)

    @classmethod
    def static_bitspan(cls):
        return sum(map(lambda x: x[1].bitspan(), cls.FIELDS))
