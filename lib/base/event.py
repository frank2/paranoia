#!/usr/bin/env python

from paranoia.base.paranoia_agent import ParanoiaAgent, ParanoiaError

__all__ = ['EventError', 'Event', 'InstantiateEvent', 'SetPropertyEvent'
           ,'NewAddressEvent', 'NewShiftEvent', 'NewSizeEvent'
           ,'SetValueEvent', 'DeclareSubregionEvent', 'MoveSubregionEvent'
           ,'RemoveSubregionEvent']

class EventError(ParanoiaError):
    pass

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
