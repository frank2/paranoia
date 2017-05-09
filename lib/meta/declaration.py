#!/usr/bin/env python

import copy
import inspect

from paranoia.base.paranoia_agent import ParanoiaAgent, ParanoiaError
from paranoia.fundamentals import dict_merge, align

__all__ = ['DeclarationError', 'Declaration', 'ensure_declaration']

class DeclarationError(ParanoiaError):
    pass

def ensure_declaration(obj):
    from paranoia.meta.region import is_region
    
    if isinstance(obj, Declaration):
        return obj
    elif is_region(obj):
        return obj.declare()
    else:
        raise DeclarationError('declaration must be either a Declaration object or a Region class')

class Declaration(ParanoiaAgent):
    BASE_CLASS = None
    ARGS = None

    def __init__(self, **kwargs):
        self.base_class = kwargs.setdefault('base_class', self.BASE_CLASS)

        if self.base_class is None:
            raise DeclarationError('base_class cannot be None')

        if not inspect.isclass(self.base_class):
            raise DeclarationError('base_class must be a class')

        self.args = kwargs.setdefault('args', self.ARGS)

        if self.args is None:
            self.args = dict()

        if not isinstance(self.args, dict):
            raise DeclarationError('args must be a dictionary object')

        self.instance = kwargs.setdefault('instance', None)

    def instantiate(self, **kwargs):
        dict_merge(kwargs, self.args)
        kwargs['declaration'] = self

        self.instance = self.base_class(**kwargs)
        return self.instance

    def get_arg(self, arg):
        if not arg in self.args:
            return getattr(self.base_class, arg.upper(), None)

        return self.args[arg]

    def set_arg(self, arg, value, from_instance=False):
        self.args[arg] = value

        if not self.instance is None and not from_instance:
            setattr(self.instance, arg, value)

    def copy(self):
        copied = self.__class__(base_class=self.base_class
                                ,args=copy.deepcopy(self.args))

        return copied

    def __repr__(self):
        return '<Declaration:%s>' % self.base_class.__name__
