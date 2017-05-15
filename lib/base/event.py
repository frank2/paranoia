#!/usr/bin/env python

import inspect

from paranoia.base.paranoia_agent import ParanoiaAgent, ParanoiaError

__all__ = ['get_event_base', 'EventError', 'Event', 'InstantiateEvent'
           ,'SetPropertyEvent', 'NewAddressEvent', 'NewShiftEvent', 'NewSizeEvent'
           ,'SetValueEvent', 'DeclareSubregionEvent', 'MoveSubregionEvent'
           ,'RemoveSubregionEvent']

class EventError(ParanoiaError):
    pass

def get_event_base(event_class):
    if isinstance(event_class, Event):
        event_class = event_class.__class__
        
    if not inspect.isclass(event_class):
        raise EventError('event class must be a class')

    if not issubclass(event_class, Event):
        raise EventError('class must derive Event')

    if event_class == Event:
        raise EventError('cannot get base of root class')

    base_class = event_class

    while not Event in base_class.__bases__:
        base_class = base_class.__bases__[0]

    return base_class

class Event(ParanoiaAgent):
    def __call__(self, *args):
        raise NotImplementedError

class InstantiateEvent(Event):
    def __call__(self, decl, instance, kwargs):
        raise NotImplementedError
    
class SetPropertyEvent(Event):
    def __call__(self, decl, prop, value):
        raise NotImplementedError

class NewAddressEvent(Event):
    def __call__(self, decl, address, shift):
        raise NotImplementedError

class NewShiftEvent(Event):
    def __call__(self, decl, shift):
        raise NotImplementedError

class NewSizeEvent(Event):
    def __call__(self, decl, old_size, new_size):
        raise NotImplementedError

class SetValueEvent(Event):
    def __call__(self, decl, value):
        raise NotImplementedError

class DeclareSubregionEvent(Event):
    def __call__(self, decl, subregion):
        raise NotImplementedError

class MoveSubregionEvent(Event):
    def __call__(self, decl, old_offset, new_offset):
        raise NotImplementedError

class RemoveSubregionEvent(Event):
    def __call__(self, decl, subregion):
        raise NotImplementedError
