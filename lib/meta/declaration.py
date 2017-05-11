#!/usr/bin/env python

import copy
import inspect

from paranoia.base.paranoia_agent import ParanoiaAgent, ParanoiaError
from paranoia.fundamentals import dict_merge, align

__all__ = ['DeclarationError', 'Declaration', 'DeclarationEventError', 'DeclarationEvent', 'SetPropertyEvent'
           ,'ensure_declaration']

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

        self.events = kwargs.setdefault('events', self.EVENTS)

        if self.events is None:
            self.events = dict()

        instance = kwargs.setdefault('instance', None)
        self.set_instance(instance)
            
    def instantiate(self, **kwargs):
        dict_merge(kwargs, self.args)
        kwargs['declaration'] = self

        self.instance = self.base_class(**kwargs)
        return self.instance

    def set_instance(self, instance):
        self.instance = instance

        if instance is None:
            return

        self.set_arg('declaration', self)
        
        for arg in self.args:
            setattr(self.instance, arg, self.args[arg])

    def has_event_class(self, event_class):
        if inspect.isclass(event_class) and issubclass(event_class, DeclarationEvent):
            event_class = event_class.EVENT_CLASS
            
        return event_class in self.events

    def has_event(self, event):
        if not isinstance(event, DeclarationEvent):
            raise DeclarationError('event must be a DeclarationEvent')

        if not self.has_event_class(event.event_class)
            return False
        
        event_list = self.events[event_class]

        return event in event_list

    def add_event(self, event):
        if not isinstance(event, DeclarationEvent):
            raise DeclarationError('event must be a DeclarationEvent')

        if self.has_event(event):
            return
        
        event_list = self.events.setdefault(event.event_class, list())
        event_list.append(event)

    def remove_event(self, event):
        if not isinstance(event, DeclarationEvent):
            raise DeclarationError('event must be a DeclarationEvent')

        if not self.has_event(event)
            raise DeclarationError('no such event')
        
        event_list = self.events[event.event_class]
        event_list.remove(event)

        if len(event_list) == 0:
            del self.events[arg]

    def trigger_event(self, event_class):
        if not self.has_event_class(event_class):
            raise DeclarationError('no such event class to trigger')

        if inspect.isclass(event_class) and issubclass(event_class, DeclarationEvent):
            event_class = event_class.EVENT_CLASS

        for event in self.events[event_class]:
            event(self)

    def get_arg(self, arg):
        if not arg in self.args:
            return getattr(self.base_class, arg.upper(), None)

        return self.args[arg]

    def set_arg(self, arg, value, from_instance=False):
        self.args[arg] = value

        if not self.instance is None and not from_instance:
            setattr(self.instance, arg, value)

        if self.has_event_class(SetPropertyEvent):
            self.trigger_event(SetPropertyEvent)

    def copy(self):
        copied = self.__class__(base_class=self.base_class
                                ,args=copy.deepcopy(self.args))

        return copied

    def __repr__(self):
        return '<Declaration:%s/%X>' % (self.base_class.__name__, id(self))

class DeclarationEventError(DeclarationError):
    pass

class DeclarationEvent(ParanoiaAgent):
    EVENT_CLASS = None
    
    def __init__(self, **kwargs):
        self.event_class = kwargs.setdefault('event_class', self.EVENT_CLASS)

        if self.event_class is None:
            raise DeclarationEventError('event_class cannot be None')

    def __call__(self, event_decl):
        raise DeclarationEventError('__call__ not implemented')

class SetPropertyEvent(DeclarationEvent):
    EVENT_CLASS = "set_property"
