#!/usr/bin/env python

from paranoia.meta import mapping

__all__ = ['UnionError', 'Union']

class UnionError(mapping.MappingError):
    pass

class Union(mapping.Mapping):
    OVERLAPS = True
