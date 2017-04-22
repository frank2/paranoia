#!/usr/bin/env python

from paranoia.base import paranoia_agent
from paranoia.fundamentals import dict_merge

__all__ = ['DeclarationError', 'Declaration']

class DeclarationError(paranoia_agent.ParanoiaError):
    pass

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
        
        if not 'size' in kwargs:
            return self.base_class.static_size(**kwargs)

        return self.args['size']

    def alignment(self):
        if 'alignment' not in self.args:
            return self.base_class.static_alignment()

        return self.args['alignment']

    def get_arg(self, arg):
        if arg not in self.args:
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
                      
