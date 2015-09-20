#!/usr/bin/env python

from . import declaration
from paranoia.base import memory_region
from paranoia.base.abstract import mapping

class StructureError(mapping.MappingError):
    pass

class Structure(mapping.Mapping):
    @classmethod
    def simple(cls, declarations):
        new_struct_declaration = list()

        if not getattr(declarations, '__iter__', None):
            raise StructureError('declarations must be a sequence of names, a base class and optional arguments')

        if len(declarations) == 0:
            raise StructureError('empty declaration list given')

        for declaration_obj in declarations:
            if not len(declaration_obj) == 2 and not len(declaration_obj) == 3:
                raise StructureError('simple declaration item has invalid arguments')

            if not isinstance(declaration_obj[0], basestring):
                raise StructureError('first argument of the declaration must be a string')

            if not issubclass(declaration_obj[1], memory_region.MemoryRegion):
                raise StructureError('second argument must be a base class implementing MemoryRegion')

            if len(declaration_obj) == 3 and not isinstance(declaration_obj[2], dict):
                raise StructureError('optional third argument must be a dictionary of arguments')
                
            if not len(declaration_obj) == 3:
                args = dict()
            else:
                args = declaration_obj[2]

            new_struct_declaration.append([declaration_obj[0]
                                          ,declaration.Declaration(base_class=declaration_obj[1]
                                                                   ,args=args)])
        
        class SimplifiedDataStructure(cls):
            FIELDS = new_struct_declaration

        return SimplifiedDataStructure
