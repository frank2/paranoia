#!/usr/bin/env python

import os

from paranoia.base.allocator import allocators, VirtualAllocator, VirtualAllocation, VirtualAddress
from paranoia.base.paranoia_agent import ParanoiaAgent, ParanoiaError
from paranoia.base.size import Size

__all__ = ['DiskError', 'DiskAddress', 'DiskAllocation', 'DiskAllocator', 'DiskManager'
           ,'DiskHandle', 'manager', 'disk_handle']
           
class DiskError(ParanoiaError):
    pass

class DiskAddress(VirtualAddress):
    def mirror(self, offset, data):
        if self.allocator.handle.closed() or not self.allocator.handle.writable():
            return
        
        ref = self.allocator.handle
        curr = ref.tell()
        ref.seek(offset)
        ref.write(data)
        ref.seek(curr)

    def fork(self, offset):
        alloc_offset = int(self)+offset - self.allocator.base_address
        
        if self.allocator.handle.writable() and alloc_offset > self.allocator.maximum_offset:
            self.allocator.maximum_offset = alloc_offset

        return super(DiskAddress, self).fork(offset)

    def write_byte(self, value, offset=0):
        super(DiskAddress, self).write_byte(value, offset)
        self.mirror(int(self) - self.allocator.base_address + offset, chr(value))

    def write_bytestring(self, string, offset=0, force=False, direct=False):
        super(DiskAddress, self).write_bytestring(string, offset, force, direct)
        self.mirror(int(self) - self.allocator.base_address + offset, string)

    def write_string(self, string, offset=0, encoding='ascii', force=False, direct=False):
        super(DiskAddress, self).write_string(string, offset, encoding, force, direct)
        self.mirror(int(self) - self.allocator.base_address + offset, string)

    def write_bytes(self, byte_list, offset=0, force=False, direct=False):
        super(DiskAddress, self).write_bytes(byte_list, offset, force, direct)
        self.mirror(int(self) - self.allocator.base_address + offset, bytearray(byte_list))

    def write_bits(self, bit_list, bit_offset=0, force=False, direct=False):
        super(DiskAddress, self).write_bits(bit_list, bit_offset, force, direct)
        block_address = self.fork(int(bit_offset/8))
        block_size = Size(bits=bit_offset % 8 + len(bit_list)).byte_length()
        block_data = block_address.read_bytes(size=block_size)
        self.mirror(int(self) - self.allocator.base_address + int(bit_offset/8), bytearray(block_data))

class DiskAllocation(VirtualAllocation):
    def address(self, offset=0):
        if offset >= self.size:
            return self.allocator.address(offset)

        if not offset in self.addresses:
            self.addresses[offset] = DiskAddress(offset=offset
                                                 ,allocation=self
                                                 ,allocator=self.allocator)
        
        return self.addresses[offset]
        
    def read_byte(self, id_val):
        self.check_id()

        offset = id_val - self.allocator.base_address

        if offset > self.size: # data unread
            handle = self.allocator.handle

            if handle.closed():
                raise DiskError('offset out of range on unopened file')
            
            curr = handle.tell()
            handle.seek(offset, os.SEEK_SET)
            pos = self.dataref.tell()

            if not pos == offset:
                raise DiskError('offset exceeds backing file')
            
            data = self.dataref.read_address(1)
            handle.seek(curr, os.SEEK_SET)

            if data is None:
                raise EOFError

            address, size = data

            if size == 0:
                raise EOFError

            if not address.allocation == self:
                return ord(address.read_byte())

        self.allocator.check_range(id_val)

        mem_addr = self.allocator.memory_address(id_val)
        backing_alloc = self.allocator.backing_allocations[self.id]
        return backing_alloc.read_byte(mem_addr)
    
    def write_byte(self, id_val, byte_val):
        self.check_id()

        file_offset = id_val - self.allocator.base_address
        alloc_offset = id_val - self.id

        if alloc_offset+1 > self.size: # buffer not large enough
            if self.allocator.handle.closed() or not self.allocator.handle.writable():
                raise DiskError('write exceeds file boundary while file is unwritable')
            
            self.allocator.maximum_offset = file_offset+1
            self.reallocate(alloc_offset+1)
            handle = self.allocator.handle
            curr = handle.tell()
            handle.seek(file_offset, os.SEEK_SET)
            pos = self.dataref.tell()

            if not pos == file_offset:
                zero_delta = file_offset - pos
                self.handle.write('\x00' * zero_delta, False)
                
            handle.write(chr(byte_val), False)
            handle.seek(curr, os.SEEK_SET)

        self.allocator.check_range(id_val)

        mem_addr = self.allocator.memory_address(id_val)
        backing_alloc = self.allocator.backing_allocations[self.id]
        return backing_alloc.write_byte(mem_addr, byte_val)

    def read_bytestring(self, id_val, size=None, force=False, direct=False):
        self.check_id()

        offset = id_val - self.allocator.base_address

        if size is None:
            size = self.allocator.maximum_offset - offset

        if offset+size > self.size: # data unread
            handle = self.allocator.handle

            if handle.closed():
                raise DiskError('offset and data size exceed boundaries of closed file')
            
            curr = handle.tell()
            handle.seek(offset, os.SEEK_SET)
            pos = handle.tell()

            if not pos == offset:
                raise DiskError('offset exceeds backing file')
            
            data = handle.read_address(size)
            handle.seek(curr, os.SEEK_SET)

            if data is None:
                raise EOFError

            address, size = data

            if size == 0:
                raise EOFError

            if not address.allocation == self:
                return ord(address.read_bytestring(size=size))

        self.allocator.check_range(id_val)

        mem_addr = self.allocator.memory_address(id_val)
        backing_alloc = self.allocator.backing_allocations[self.id]
        return backing_alloc.read_bytestring(mem_addr, size=size, force=force, direct=direct)

    def write_bytestring(self, id_val, string, force=False, direct=False):
        self.check_id()

        alloc_offset = id_val - self.id
        file_offset = id_val - self.allocator.base_address
        size = len(string)
        
        if alloc_offset+size > self.size: # buffer too small
            if self.allocator.handle.closed() or not self.allocator.handle.writable():
                raise DiskError('write exceeds file boundary while file is unwritable')
            
            handle = self.allocator.handle
            self.allocator.maximum_offset = file_offset+len(string)
            self.reallocate(alloc_offset+size)
            curr = handle.tell()
            handle.seek(file_offset, os.SEEK_SET)
            pos = handle.tell()

            if not pos == file_offset:
                zero_delta = file_offset - pos
                handle.write('\x00' * zero_delta, False)
                
            handle.write(string, False)
            handle.seek(curr, os.SEEK_SET)

        self.allocator.check_range(id_val)

        mem_addr = self.allocator.memory_address(id_val)
        backing_alloc = self.allocator.backing_allocations[self.id]
        return backing_alloc.write_bytestring(mem_addr, string, force=force, direct=direct)

    def flush(self, id_val=None, size=None):
        if not self.buffer:
            # everything is technically flushed, skip
            return

        if id_val is None:
            id_val = self.id

        self.check_id_range(id_val)
        backing_alloc = self.allocator.backing_allocations[self.id]
        
        if size is None:
            size = backing_alloc.size

        if size == 0:
            return

        start_delta = id_val - self.id

        if size == self.size and not start_delta == 0:
            end_delta = size - start_delta
        else:
            end_delta = start_delta + size

        backing_address = backing_alloc.id + start_delta
        file_delta = id_val - self.allocator.base_address
        block_range = list()

        if size == 1:
            block = backing_alloc.get_block(backing_address)

            if not block.value is None:
                block.flush()
                
            return

        handle = self.allocator.handle
        curr = handle.tell()

        for i in range(start_delta, end_delta+1):
            if not i == end_delta and i in backing_alloc.blocks and not backing_alloc.blocks[i].value is None and len(block_range) == 0:
                block_range.append(i)
            elif i == end_delta or (not i in backing_alloc.blocks or backing_alloc.blocks[i].value is None) and len(block_range) == 1:
                if len(block_range) == 0: # end of data
                    break
                
                block_range.append(i)

                block_start, block_end = block_range
                byte_array = bytearray(map(lambda x: backing_alloc.blocks[x].value, range(*block_range)))
                
                long = getattr(__builtin__, 'long', None)

                if not long is None: # python 2
                    string_buffer = ctypes.create_string_buffer(str(byte_array))
                else:
                    string_buffer = ctypes.create_string_buffer(byte_array)

                string_address = ctypes.addressof(string_buffer)

                memmove(backing_address+block_start, string_address, len(byte_array))

                if not handle.closed() and handle.writable():
                    handle.seek(file_delta + block_start, os.SEEK_SET)
                    handle.write(byte_array, False)

                for i in range(*block_range):
                    backing_alloc.blocks[i].value = None

                block_range = list()

        handle.seek(curr, os.SEEK_SET)

class DiskAllocator(VirtualAllocator):
    ALLOCATION_CLASS = DiskAllocation
    HANDLE = None

    def __init__(self, **kwargs):
        super(DiskAllocator, self).__init__(**kwargs)

        self.handle = kwargs.setdefault('handle', self.HANDLE)

        if self.handle is None:
            raise DiskError('handle cannot be None')

        if not isinstance(self.handle, DiskHandle):
            raise DiskError('handle must be a DiskHandle object')

    def address(self, offset=0):
        if offset > self.maximum_offset and not self.handle.writable():
            raise DiskError('offset %d greater than maximum offset %d' % (offset, self.maximum_offset))
        
        offset_addr = self.offset_address(offset)

        if offset_addr in self.allocations:
            return self.allocations[offset_addr].value.address()
        
        allocation = self.find(offset_addr)

        if not allocation is None:
            offset = offset_addr - allocation.id
            return allocation.address(offset)

        return DiskAddress(offset=offset, allocator=self)

class DiskManager(ParanoiaAgent):
    def __init__(self, **kwargs):
        self.files = dict()
        self.allocators = dict()
        self.last_eof = dict()

    def open(self, filename, mode, buffer=False):
        if 'r' in mode and 'w' in mode or '+' in mode:
            if not os.path.exists(filename):
                fp = open(filename, 'w')
                fp.close()
                
        fp = open(filename, mode)
        return self.manage(fp)

    def manage(self, file_object):
        self.files[file_object.fileno()] = file_object

        file_object.seek(0, os.SEEK_END)
        maximum = file_object.tell()
        file_object.seek(0, os.SEEK_SET)
        
        handle = DiskHandle(fileno=file_object.fileno(), manager=self)
        self.allocators[file_object.fileno()] = DiskAllocator(buffer=buffer
                                                              ,maximum_offset=maximum
                                                              ,handle=handle)

        return handle

    def close(self, fileno, destroy=True):
        if not fileno in self.files:
            raise DiskError('fileno not being managed')
        
        self.flush(fileno)
        self.files[fileno].close()
        del self.files[fileno]

        if destroy:
            allocator = self.allocators[fileno]

            for address in allocator.allocations:
                allocator.free(address)
                
        del self.allocators[fileno]

        if fileno in self.last_eof:
            del self.last_eof[fileno]

    def flush(self, fileno):
        if not fileno in self.files:
            raise DiskError('fileno not being managed')

        allocator = self.allocators[fileno]

        for allocation_id in allocator.allocations:
            allocation = allocator.allocations[allocation_id].value
            allocation.flush()

        self.files[fileno].flush()

    def next(self, fileno):
        if not fileno in self.files:
            raise DiskError('fileno not being managed')

        line = self.readline(fileno)

        if line is None:
            raise StopIteration

        return line

    def read(self, fileno, size=None):
        if not fileno in self.files:
            raise DiskError('fileno not being managed')

        offset = self.tell(fileno)
        allocator = self.allocators[fileno]
        address = allocator.offset_address(offset)
        allocation = allocator.find(address)

        if size is None:
            eof = self.eof(fileno)
            size = eof - offset

        fp = self.files[fileno]
        data = fp.read(size)
        size = len(data)

        if size == 0:
            return
        
        if allocation is None:
            allocation = allocator.allocate(offset, size)

        allocation_offset = address - allocation.id
        end_offset = allocation_offset + size

        if end_offset > allocation.size:
            allocation.reallocate(end_offset)

        allocation.write_string(allocation.id+allocation_offset, data)

        return (allocation.address(allocation_offset), size)

    def readline(self, fileno, size=None):
        if not fileno in self.files:
            raise DiskError('fileno not being managed')
        
        current_position = self.tell(fileno)
        eof = self.eof()
        fp = self.files[fileno]
        char = None
        data_read = 0
        peek_position = current_position

        while not char == '\n' and (size is None or data_read < size):
            char = fp.read(1)
            data_read += 1
            peek_position += 1

            if len(char) == 0:
                break
            
            if peek_position == eof:
                eof = self.eof()

            if peek_position == eof:
                break

        self.seek(fileno, current_position)
        return self.read(fileno, data_read)

    def readlines(self, fileno, sizehint=None):
        if not fileno in self.files:
            raise DiskError('fileno not being managed')

        current_position = self.tell(fileno)
        eof = self.eof()

        lines = list()
        end_position = current_position
        
        while end_position < eof and (sizehint is None or sizehint > 0):
            line = self.readline(fileno, sizehint)

            if line is None:
                break

            lines.append(line)
            line_addr, line_size = line

            end_position += line_size

            if end_position >= eof:
                eof = self.eof()

            if end_position >= eof:
                break

            if not sizehint is None:
                sizehint -= line_size

        return lines
    
    def seek(self, fileno, offset, whence=None):
        if not fileno in self.files:
            raise DiskError('fileno not being managed')
        
        if whence is None:
            whence = os.SEEK_SET

        self.files[fileno].seek(offset, whence)

    def tell(self, fileno):
        if not fileno in self.files:
            raise DiskError('fileno not being managed')

        return self.files[fileno].tell()

    def write(self, fileno, data):
        if not fileno in self.files:
            raise DiskError('fileno not being managed')

        self.files[fileno].write(data)

    def writelines(self, fileno, lines):
        self.write(fileno, ''.join(lines))

    def readable(self, fileno):
        if not fileno in self.files:
            raise DiskError('fileno not being managed')

        mode = self.files[fileno].mode
        
        return 'r' in mode or '+' in mode

    def writable(self, fileno):
        if not fileno in self.files:
            raise DiskError('fileno not being managed')

        mode = self.files[fileno].mode
        
        return 'w' in mode or '+' in mode or 'a' in mode
        
    def eof(self, fileno):
        if not fileno in self.files:
            raise DiskError('fileno not being managed')
        
        current = self.tell(fileno)
        self.seek(fileno, 0, os.SEEK_END)
        eof = self.tell(fileno)
        self.seek(fileno, current)

        if not fileno in self.last_eof:
            self.last_eof[fileno] = eof
        elif eof < self.last_eof[fileno]:
            raise DiskError('file truncated')

        allocator = self.allocators[fileno]
        allocator.maximum_offset = eof
        
        return eof

    def closed(self, fileno):
        if fileno is None or not fileno in self.files:
            return True

        return self.files[fileno].closed

    def allocator(self, fileno):
        if not fileno in self.files:
            raise DiskError('fileno not being managed')

        return self.allocators[fileno]

    def allocations(self, fileno):
        if not fileno in self.files:
            raise DiskError('fileno not being managed')

        allocator = self.allocator(fileno)

        return allocator.allocations.values()

manager = DiskManager()

class DiskHandle(ParanoiaAgent):
    MANAGER = manager
    FILENO = None
    
    def __init__(self, **kwargs):
        self.manager = kwargs.setdefault('manager', self.MANAGER)

        if self.manager is None:
            raise DiskError('manager cannot be None')

        if not isinstance(self.manager, DiskManager):
            raise DiskError('manager must be a DiskManager instance')

        self.fileno = kwargs.setdefault('fileno', self.FILENO)

        if self.fileno is None:
            raise DiskError('fileno cannot be None')

    def close(self, destroy=True):
        self.manager.close(self.fileno, destroy)
        self.fileno = None

    def flush(self):
        self.manager.flush(self.fileno)

    def next(self):
        return self.manager.next(self.fileno)

    def read_address(self, size=None):
        return self.manager.read(self.fileno, size)

    def readline_address(self, size=None):
        return self.manager.readline(self.fileno, size)

    def readlines_address(self, sizehint=None):
        return self.manager.readlines(self.fileno, self.size)

    def read(self, size=None):
        data = self.read_address(size)

        if not data is None:
            address, size = data
            return address.read_string(size=size)
        else:
            return ''

    def readline(self, size=None):
        data = self.readline_address(size)

        if not data is None:
            address, size = data
            return address.read_string(size=size)

    def readlines(self, size=None):
        line_data = list()
        lines = self.readline_address(size)

        for line in lines:
            address, size = line
            line_data.append(address.read_string(size=size))

        return line_data

    def seek(self, offset, whence=None):
        self.manager.seek(self.fileno, offset, whence)

    def tell(self):
        return self.manager.tell(self.fileno)

    def tell_address(self):
        allocator = self.manager.allocators[self.fileno]
        return allocator.address(self.tell())

    def write_address(self, data, mirror=True):
        offset = self.tell()
        self.manager.write(self.fileno, data)

        if mirror:
            return self.mirror(offset, data)

    def writelines_address(self, lines, mirror=True):
        offset = self.tell()
        self.manager.writelines(self.fileno, lines)

        if mirror:
            return self.mirror(offset, ''.join(lines))

    def write(self, data, mirror=True):
        self.write_address(data, mirror)

    def writelines(self, data, mirror=True):
        self.writelines_address(data, mirror)

    def readable(self):
        return self.manager.readable(self.fileno)

    def writable(self):
        return self.manager.writable(self.fileno)

    def mirror(self, offset, data):
        allocator = self.manager.allocators[self.fileno]

        # if we're mirroring, we've likely already written-- set the new maximum
        allocator.maximum_offset = self.eof()
        
        offset_address = allocator.offset_address(offset)
        allocation = allocator.find(offset_address)

        if allocation is None:
            allocation = allocator.allocate(offset, len(data))
        elif offset+len(data) > allocation.size:
            allocation.reallocate(offset+len(data))

        if isinstance(data, (bytearray, bytes)):
            allocation.write_bytestring(offset_address, data)
        elif isinstance(data, (str, unicode)):
            allocation.write_string(offset_address, data)

        return (allocation.address(offset_address - allocation.id), len(data))

    def eof(self):
        return self.manager.eof(self.fileno)

    def closed(self):
        return self.manager.closed(self.fileno)

    def allocator(self):
        return self.manager.allocator(self.fileno)

    def allocations(self):
        return self.manager.allocations(self.fileno)
    
    def address(self, offset=None):
        if offset is None:
            offset = 0

        allocator = self.allocator()
        return allocator.address(offset)

    def allocate(self, offset=0, size=None):
        if size is None:
            size = self.eof() - offset

        allocator = self.allocator()
        alloc_addr = allocator.offset_address(offset)
        allocation = allocator.find(alloc_addr)

        if not allocation is None:
            raise DiskError('offset already allocated')

        return allocator.allocate(offset, size)

    def __iter__(self):
        if not self.closed():
            return self

def disk_handle(filename, mode):
    global manager
    return manager.open(filename, mode)
