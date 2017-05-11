#!/usr/bin/env python

import copy
import inspect

from paranoia.base.paranoia_agent import ParanoiaAgent, ParanoiaError
from paranoia.base.event import *
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
    EVENTS = None

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

        self.events = kwargs.setdefault('events', self.EVENTS)

        if self.events is None:
            self.events = list()

        instance = kwargs.setdefault('instance', None)
        self.set_instance(instance)

    def has_event(self, event):
        if not isinstance(event, Event):
            raise DeclarationError('event must be an Event')

        return event in self.events

    def add_event(self, event):
        if not isinstance(event, Event):
            raise DeclarationError('event must be an Event')

        if self.has_event(event):
            return
        
        self.events.append(event)

    def insert_event(self, index, event):
        if not isinstance(event, Event):
            raise DeclarationError('event must be an Event')

        if self.has_event(event):
            return
        
        self.events.insert(index, event)
        
    def remove_event(self, event):
        if not isinstance(event, Event):
            raise DeclarationError('event must be an Event')

        if not self.has_event(event):
            raise DeclarationError('no such event')
        
        self.events.remove(event)

    def trigger_event(self, event_class, *args):
        if not issubclass(event_class, Event):
            raise DeclarationError('event class must be an Event class')

        events_available = filter(lambda x: isinstance(x, event_class), self.events)
        
        for event in events_available:
            event(self, *args)
            
    def instantiate(self, **kwargs):
        dict_merge(kwargs, self.args)
        kwargs['declaration'] = self

        self.instance = self.base_class(**kwargs)
        self.trigger_event(InstantiateEvent, self.instance, kwargs)
        
        return self.instance

    def set_instance(self, instance):
        self.instance = instance

        if instance is None:
            return

        self.set_arg('declaration', self)
        
        for arg in self.args:
            setattr(self.instance, arg, self.args[arg])

    def get_arg(self, arg):
        if not arg in self.args:
            return getattr(self.base_class, arg.upper(), None)

        return self.args[arg]

    def set_arg(self, arg, value, from_instance=False):
        self.args[arg] = value

        if not self.instance is None and not from_instance:
            setattr(self.instance, arg, value)

        self.trigger_event(SetPropertyEvent, arg, value)

    def copy(self):
        copied = self.__class__(base_class=self.base_class
                                ,args=copy.deepcopy(self.args))

        return copied

    def __repr__(self):
        return '<Declaration:%s/%X>' % (self.base_class.__name__, id(self))
