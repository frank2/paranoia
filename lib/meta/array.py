#!/usr/bin/env python

import inspect

from paranoia.fundamentals import align, alignment_delta
from paranoia.base.size import Size
from paranoia.base.event import *
from paranoia.meta.declaration import ensure_declaration
from paranoia.meta.region import Region, RegionError, RegionDeclaration, RegionDeclarationError

__all__ = ['ArrayDeclarationError', 'ArrayDeclaration', 'ArrayError', 'Array']

class ArrayDeclarationError(RegionDeclarationError):
    pass

class ArrayDeclaration(RegionDeclaration):
    def __init__(self, **kwargs):
        args = kwargs.get('args')

        if args is None:
            args = dict()
            kwargs['args'] = args

        base_declaration = args.get('base_declaration')

        if base_declaration is None:
            raise ArrayDeclarationError('base declaration cannot be None')

        args['base_declaration'] = ensure_declaration(base_declaration)
        elements = args.get('elements')

        if elements is None:
            elements = 0
            args['elements'] = 0
            
        super(ArrayDeclaration, self).__init__(**kwargs)

        self.declaration_index = dict()
        
        if not elements == 0:
            self.set_arg('elements', 0)
            self.set_elements(elements)

    def declarative_size(self, **kwargs):
        elements = self.get_arg('elements')

        if elements == 0:
            return Size(bits=0)

        base_decl = self.get_arg('base_declaration')

        if base_decl is None:
            raise ArrayDeclarationError('base declaration cannot be None')

        base_size = base_decl.size()
        alignment = base_decl.get_arg('alignment')
        returned_size = self.aligned_offset(elements)

        if not alignment == 0:
            returned_size -= alignment_delta(int(base_size), alignment)

        return returned_size

    def set_elements(self, elements):
        elem_arg = self.get_arg('elements')
        
        if elements == elem_arg and not Force:
            return

        self.set_arg('elements', elements)
        
        base_decl = self.get_arg('base_declaration')

        if base_decl is None:
            raise ArrayDeclarationError('base_declaration cannot be None')

        shift = self.get_arg('shift')
        base_size = base_decl.size()
        alignment = base_decl.get_arg('alignment')
        new_size = self.aligned_offset(elements)

        if not alignment == 0:
            new_size -= alignment_delta(base_size, alignment)
        
        if elements < elem_arg and not self.current_offsets.is_empty():
            filter_key = self.aligned_offset(index)
            kill_set = set()
            nodes = [self.current_offsets.root]

            while len(nodes) > 0:
                node = nodes.pop(0)

                if filter_key >= node.label:
                    kill_set.add(node.label)
                    
                    if not node.left is None:
                        nodes.append(node.left)
                        
                if not node.right is None:
                    nodes.append(node.right)

            for kill in kill_set:
                decl_id = self.reverse_offsets[kill].keys()[0]
                kill_decl = self.subregions[decl_id]
                del self.declaration_index[kill]
                self.remove_subregion(kill_decl)

        self.set_size(new_size)

    def aligned_offset(self, index):
        base_decl = self.get_arg('base_declaration')

        if base_decl is None:
            raise ArrayDeclarationError('base declaration cannot be None')

        shift = self.get_arg('shift')
        decl_size = int(base_decl.size())
        return (base_decl.align(decl_size, shift) - shift) * index

    def declare_index(self, index):
        if index in self.declaration_index:
            return self.declaration_index[index]

        base_decl = self.get_arg('base_declaration')

        if base_decl is None:
            raise ArrayDeclarationError('base declaration cannot be None')

        copied_decl = base_decl.copy()
        index_offset = self.aligned_offset(index)
        
        self.declaration_index[index] = id(copied_decl)
        self.declare_subregion(copied_decl, index_offset)

        return copied_decl

    def get_elements(self):
        return self.get_arg('elements')

class ArrayError(RegionError):
    pass

class ArrayResizeEvent(NewSizeEvent):
    def __call__(self, decl, old_size, new_size):
        if not old_size == new_size:
            raise ArrayError('array elements cannot be resized')

class Array(Region):
    DECLARATION_CLASS = ArrayDeclaration
    RESIZE_EVENT = ArrayResizeEvent
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

    def instantiate(self, index, **kwargs):
        decl = self.declaration.declare_index(index)

        if decl.instance is None or 'reinstance' in kwargs and kwargs['reinstance'] == True:
            return decl.instantiate(**kwargs)

        return decl.instance

    def __getitem__(self, index):
        if index < 0:
            index += self.elements

        if index < 0 or index > self.elements:
            raise IndexError(index)

        return self.instantiate(index)

    def __setitem__(self, index, value):
        self.instantiate(index).set_value(value)

    def __len__(self):
        return self.elements

    def __iter__(self):
        for i in xrange(len(self)):
            yield self.instantiate(i)
        
    @classmethod
    def static_size(cls, **kwargs):
        base_decl = kwargs.setdefault('base_declaration', cls.BASE_DECLARATION)
        
        if base_decl is None:
            raise ArrayError('no base declaration to get base size from')

        base_decl = ensure_declaration(base_decl)
        base_size = base_decl.size()
        elements = kwargs.setdefault('elements', cls.ELEMENTS)
        shift = kwargs.setdefault('shift', cls.SHIFT)
        size = base_decl.align(base_size, shift) * elements
        alignment = base_decl.get_arg('alignment')

        if not alignment == 0:
            size -= alignment_delta(base_size, alignment)

        return size
        
    @classmethod
    def subclass(cls, **kwargs):
        kwargs.setdefault('declaration_class', cls.DECLARATION_CLASS)
        kwargs.setdefault('resize_event', cls.RESIZE_EVENT)
        kwargs.setdefault('base_declaration', cls.BASE_DECLARATION)
        kwargs.setdefault('elements', cls.ELEMENTS)

        super_class = super(Array, cls).subclass(**kwargs)

        class SubclassedArray(super_class):
            DECLARATION_CLASS = kwargs['declaration_class']
            RESIZE_EVENT = kwargs['resize_event']
            BASE_DECLARATION = kwargs['base_declaration']
            ELEMENTS = kwargs['elements']

        return SubclassedArray

ArrayDeclaration.BASE_CLASS = Array
