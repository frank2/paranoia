#!/usr/bin/env python

from .. import paranoia_agent, size_hint

# declarations should be aware of the SizeHint subclass. it should be a special
# case.
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

    def is_size_hint(self):
        return issubclass(self.base_class, size_hint.SizeHint)

    def instantiate(self, memory_base=None, bitshift=0, parent=None):
        # make a copy of our argument instantiation
        arg_dict = dict(self.args.items()[:])
        arg_dict['memory_base'] = memory_base
        arg_dict['bitshift'] = bitshift
        arg_dict['parent_region'] = parent

        return self.base_class(**arg_dict)

    def bitspan(self):
        if not self.args.has_key('bitspan'):
            return self.base_class.static_bitspan(**self.args)

        return self.args['bitspan']

    def alignment(self):
        if not self.args.has_key('alignment'):
            return self.base_class.static_alignment()

        return self.args['alignment']

    def my_declaration(self):
        if not self.is_size_hint():
            raise DeclarationError('declaration is not a size hint')

        if not self.args.has_key('my_declaration'):
            return self.base_class.MY_DECLARATION

        return self.args['my_declaration']

    def target_declaration(self):
        if not self.is_size_hint():
            raise DeclarationError('declaration is not a size hint')

        if not self.args.has_key('target_declaration'):
            return self.base_class.TARGET_DECLARATION

        return self.args['target_declaration']

    def argument(self):
        if not self.is_size_hint():
            raise DeclarationError('declaration is not a size hint')

        if not self.args.has_key('argument'):
            return self.base_class.ARGUMENT

        return self.args['argument']
