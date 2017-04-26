#!/usr/bin/env python

from paranoia.base import paranoia_agent
from paranoia.fundamentals import dict_merge, align

__all__ = ['DeclarationError', 'Declaration', 'ensure_declaration']

class DeclarationError(paranoia_agent.ParanoiaError):
    pass

def ensure_declaration(obj):
    from paranoia.meta.region import is_region_class
    
    if isinstance(obj, Declaration):
        return obj
    elif is_region_class(obj):
        return obj.declare()
    else:
        raise DeclarationError('declaration must be either a Declaration object or a Region class')

class Declaration(paranoia_agent.ParanoiaAgent):
    BASE_CLASS = None
    ARGS = None

    def __init__(self, **kwargs):
        from paranoia.meta.region import is_region
        
        self.base_class = kwargs.setdefault('base_class', self.BASE_CLASS)

        if self.base_class is None:
            raise DeclarationError('base_class cannot be None')

        if not is_region(self.base_class):
            raise DeclarationError('base_class must implement Region')

        self.args = kwargs.setdefault('args', self.ARGS)

        if self.args is None:
            self.args = dict()

        if not isinstance(self.args, dict):
            raise DeclarationError('args must be a dictionary object')

        self.instance = None

    def instantiate(self, **kwargs):
        dict_merge(kwargs, self.args)
        kwargs['declaration'] = self

        self.instance = self.base_class(**kwargs)
        return self.instance

    def size(self, **kwargs):
        dict_merge(kwargs, self.args)

        size = self.get_arg('size')
        
        if size is None:
            return self.base_class.static_size(**kwargs)

        return size

    def blockspan(self, **kwargs):
        size = self.size(**kwargs)
        shift = self.get_arg('shift')
        return int(align(int(size)+shift, 8)/8)

    def alignment(self):
        alignment = self.get_arg('alignment')
        
        if alignment is None:
            return self.base_class.static_alignment()

        return alignment

    def volatile(self):
        return self.get_arg('volatile')

    def bit_parser(self, **kwargs):
        dict_merge(kwargs, self.args)
        
        return self.base_class.bit_parser(**kwargs)

    def get_arg(self, arg):
        if not arg in self.args:
            return getattr(self.base_class, arg.upper(), None)

        return self.args[arg]

    def set_arg(self, arg, value):
        self.args[arg] = value

    def copy(self):
        copied = Declaration(base_class=self.base_class
                             ,args=dict(list(self.args.items())[:]))

        return copied

    def __repr__(self):
        return '<Declaration:%s>' % self.base_class.__name__
                      
