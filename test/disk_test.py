#!/usr/bin/env python

from paranoia.base.disk import disk_file
import os

os.remove('dongs.txt')
fp = disk_file('dongs.txt', 'r+')
print 'read:', repr(fp.read())
fp.write('dongs dongs dongs')
fp.flush()
fp.seek(0, os.SEEK_SET)
print 'read:', repr(fp.read())
fp.seek(64, os.SEEK_SET)
fp.write('dongs tho')
fp.flush()
fp.close()
fp = disk_file('dongs.txt', 'rb')
print 'read:', repr(fp.read())
fp.close()
fp = disk_file('dongs.txt', 'r+')
fp.seek(32, os.SEEK_SET)
fp.write('dongs for real')
fp.seek(0, os.SEEK_SET)
print 'read:', repr(fp.read())
