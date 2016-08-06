#!/usr/bin/env python

from paranoia.meta import mapping

__all__ = ['UnionError', 'Union']

class UnionError(mapping.MappingError):
    pass

class Union(mapping.Mapping):
    def calculate_offsets(self, start_from=0):
        self.declaration_offsets = dict()
        
        for i in range(len(self.declarations)):
            declaration = self.declarations[i]
            declaration_hash = hash(declaration)
            offset_dict = dict()

            bitspan = declaration.bitspan()
            alignment = declaration.alignment()

            offset_dict['memory_offset'] = 0
            offset_dict['bitshift'] = self.bitshift
            offset_dict['bitspan'] = bitspan

            self.declaration_offsets[declaration_hash] = offset_dict

    def calculate_length(self):
        longest_object = 0
        
        for i in range(len(self.declarations)):
            decl = self.declarations[i]
            decl_hash = hash(decl)
            decl_bitspan = self.declaration_offsets[decl_hash]['bitspan']
            
            if decl_bitspan > longest_object:
                longest_object = decl_bitspan

        self.bitspan = longest_object

    @classmethod
    def static_bitspan(cls, **kwargs):
        return max([x[1].bitspan() for x in kwargs.setdefault('fields', cls.FIELDS)])
