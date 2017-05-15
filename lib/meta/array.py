#!/usr/bin/env python

import inspect

from paranoia.fundamentals import align
from paranoia.base import Size
from paranoia.meta.declaration import ensure_declaration
from paranoia.meta.region import RegionDeclaration
from paranoia.meta.list import ListDeclarationError, ListDeclaration, ListError, List

__all__ = ['ArrayDeclarationError', 'ArrayDeclaration', 'ArrayError', 'Array']

class ArrayDeclarationError(ListDeclarationError):
    pass

class ArrayDeclaration(ListDeclaration):
    def __init__(self, **kwargs):
        args = kwargs.setdefault('args', dict())
        base_class = kwargs.setdefault('base_class', None)

        if base_class is None:
            raise ArrayDeclarationError('base_class cannot be None')

        base_decl = args.setdefault('base_declaration', base_class.BASE_DECLARATION)

        if base_decl is None:
            raise ArrayDeclarationError('base_declaration cannot be None')

        base_decl = ensure_declaration(base_decl)
        elements = args.setdefault('elements', base_class.ELEMENTS)

        args['base_declaration'] = base_decl
        args['elements'] = elements
        args['declarations'] = [base_decl.copy() for i in xrange(elements)]
        
        super(ArrayDeclaration, self).__init__(**kwargs)

    def set_elements(self, elements):
        elem_arg = self.get_arg('elements')
        
        if elements == elem_arg:
            return

        self.set_arg('elements', elements)
        
        base_decl = self.get_arg('base_declaration')

        if base_decl is None:
            raise ArrayDeclarationError('base_declaration cannot be None')

        shift = self.get_arg('shift')
        
        if elements < elem_arg:
            decls = self.get_arg('declarations')
            truncated = decls[:elements]
            erased = decls[elements:]
            self.set_arg('declarations', truncated)
            
            for dead_decl in reversed(erased):
                del self.declaration_index[id(dead_decl)]
                self.remove_subregion(dead_decl)

            self.set_size(self.declarative_size())
        elif elements > elem_arg:
            old_length = elem_arg
            element_delta = elements - old_length
            new_decls = [base_decl.copy() for i in xrange(element_delta)]
            decls = self.get_arg('declarations')
            new_index = len(decls)
            decls += new_decls

            self.set_arg('declarations', decls)
            self.set_size(self.declarative_size())

            for decl_index in range(new_index, len(decls)):
                new_decl = decls[decl_index]
                
                if decl_index == 0:
                    offset = 0
                else:
                    prev_decl = decls[decl_index-1]
                    prev_offset = self.subregion_offsets[id(prev_decl)]
                    offset = new_decl.align(prev_offset+int(prev_decl.size()), shift) - shift
                    
                self.declaration_index[id(new_decl)] = decl_index
                self.declare_subregion(new_decl, offset)

    def get_elements(self):
        return self.get_arg('elements')

class ArrayError(ListError):
    pass

class Array(List):
    DECLARATION_CLASS = ArrayDeclaration
    BASE_DECLARATION = None
    ELEMENTS = 0

    def __init__(self, **kwargs):
        self.base_declaration = kwargs.setdefault('base_declaration', self.BASE_DECLARATION)
        self.elements = kwargs.setdefault('elements', self.ELEMENTS)

        super(Array, self).__init__(**kwargs)

    def set_elements(self, elements):
        if self.is_bound():
            raise ArrayError('cannot resize bound array')

        self.declaration.set_elements(elements)

    def get_elements(self):
        return self.declaration.get_elements()

    @classmethod
    def static_size(cls, **kwargs):
        base_decl = kwargs.setdefault('base_declaration', cls.BASE_DECLARATION)
        
        if base_decl is None:
            raise ArrayError('no base declaration to get base size from')

        base_decl = ensure_declaration(base_decl)
        base_size = base_decl.size()
        elements = kwargs.setdefault('elements', cls.ELEMENTS)
        return base_size * elements

    @classmethod
    def bit_parser(cls, **kwargs):
        base_decl = kwargs.setdefault('base_declaration', cls.BASE_DECLARATION)
        
        if base_decl is None:
            raise ArrayError('no base declaration to get base bitspan from')

        base_decl = ensure_declaration(base_decl)
        elements = kwargs.setdefault('elements', cls.ELEMENTS)
        kwargs['declarations'] = [base_decl.copy() for i in xrange(elements)]
        
        return super(Array, cls).bit_parser(**kwargs)
        
    @classmethod
    def subclass(cls, **kwargs):
        kwargs.setdefault('base_declaration', cls.BASE_DECLARATION)
        kwargs.setdefault('elements', cls.ELEMENTS)

        super_class = super(Array, cls).subclass(**kwargs)

        class SubclassedArray(super_class):
            BASE_DECLARATION = kwargs['base_declaration']
            ELEMENTS = kwargs['elements']

        return SubclassedArray

ArrayDeclaration.BASE_CLASS = Array
