#!/usr/bin/env python

from setuptools import setup

setup(
    name = 'paranoia'
    ,version = '0.7.0'
    ,author = 'frank2'
    ,author_email = 'frank2@dc949.org'
    ,description = 'A data structure library.'
    ,license = 'GPLv3'
    ,keywords = 'data_structures ctypes'
    ,url = 'https://github.com/frank2/paranoia'
    ,package_dir = {'paranoia': 'lib'}
    ,packages = ['paranoia', 'paranoia.base', 'paranoia.meta', 'paranoia.types']
    ,long_description = '''PARANOiA, named after the series of DDR songs, is a library for data structures
and general manipulation of binary and executable data. It is capable of creating dynamic structures
that can be resized based on elements given and comes with a more flexible interface for creating
structures than c-types (hopefully!).'''
    ,classifiers = [
        'Development Status :: 4 - Beta'
        ,'Topic :: Software Development :: Libraries'
        ,'License :: OSI Approved :: GNU General Public License v3 (GPLv3)']
)
