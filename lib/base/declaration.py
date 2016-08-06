#!/usr/bin/env python

from paranoia.base import paranoia_agent
from paranoia.converters import dict_merge

__all__ = ['DeclarationError', 'Declaration']

class DeclarationError(paranoia_agent.ParanoiaError):
    pass

class Declaration(paranoia_agent.ParanoiaAgent):
    BASE_CLASS = None
    ARGS = None

    def __init__(self, **kwargs):
        self.base_class = kwargs.setdefault('base_class', self.BASE_CLASS)

        if self.base_class is None:
            raise DeclarationError('base_class cannot be None')

        self.args = kwargs.setdefault('args', self.ARGS)

        if self.args is None:
            self.args = dict()

        if not isinstance(self.args, dict):
            raise DeclarationError('args must be a dictionary object')

    def instantiate(self, **kwargs):
        dict_merge(kwargs, self.args)
        kwargs['declaration'] = self

        return self.base_class(**kwargs)

    def bitspan(self, **kwargs):
        if 'bitspan' not in self.args:
            return self.base_class.static_bitspan(**self.args)

        return self.args['bitspan']

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
