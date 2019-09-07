#!/usr/bin/python
#
# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import collections
import struct
import math
from .util import WIDTH_SYMBOLS, ElfhexError


class Program:
    '''The representation of an ELFHex program, which consists of segments.'''

    def __init__(self, metadata, segments):
        '''Create a new program with the provided metadata and segment list.'''
        self.segments = [(segment.name, segment)
                         for segment in segments if segment]
        self.metadata = metadata
        self.label_locations_set = False

    def get_segments(self):
        '''Returns the segments in the program.'''
        return self.segments

    def get_metadata(self):
        '''Returns the program metadata.'''
        return self.metadata

    def get_label_location(self, label_name):
        '''Returns the memory location of a label. Must call set_label_locations first.'''
        self._check_label_locations_set()
        for _, segment in self.segments:
            for _, label in segment.labels.items():
                if label.name == label_name:
                    return label.absolute_location
        raise ElfhexError(
            f'Label [{label_name}] not defined.')

    def get_memory_start(self):
        '''
        Returns the starting location of the program in memory. Must call set_label_locations
        first.
        '''
        self._check_label_locations_set()
        return self.memory_start

    def set_label_locations(self, header_size, memory_start):
        '''
        Set the location of the labels in the program, based on a header size (which will offset
        the starting location of content) and the starting location where content should be
        located in memory. Each segment will have its location in the file and memory assigned,
        with gaps appropriate for the alignment placed between each segment.
        '''
        self.label_locations_set = True
        self.memory_start = memory_start
        # leave space for header in memory
        location_in_file = header_size
        location_in_memory = memory_start + \
            self._shift_to_align(header_size, self.metadata.align)
        for _, segment in self.segments:
            # ensures segment is properly aligned in memory
            position_shift = location_in_file % segment.get_align(
                self.metadata.align)
            location_in_memory += position_shift - \
                (location_in_memory % segment.get_align(self.metadata.align))
            segment.set_location(location_in_file, location_in_memory)

            for label in segment.labels.values():
                label.set_absolute_location(location_in_memory)

            location_in_file += segment.get_file_size()
            location_in_memory += self._shift_to_align(
                segment.get_size(), self.metadata.align)

    def render(self):
        '''Return the binary representation of the program.'''
        self._check_label_locations_set()
        output = b''
        all_labels = self._collate_labels()
        for _, segment in self.segments:
            output += segment.render(all_labels, self.metadata.endianness)
        return output

    def _collate_labels(self):
        all_labels = collections.defaultdict(dict)
        for segment_name, segment in self.segments:
            for label_name, label in segment.labels.items():
                all_labels[segment_name][label_name] = label
        return all_labels

    def _check_label_locations_set(self):
        if not self.label_locations_set:
            raise ElfhexError(
                'Illegal operation performed before label locations were set.')

    def _shift_to_align(self, n, alignment):
        return math.ceil(n / alignment) * alignment


Metadata = collections.namedtuple(
    'Metadata',
    ['machine', 'endianness', 'align']
)


class Segment:
    '''A segment in an ELFHex program.'''

    def __init__(self, name, args, contents, auto_labels):
        '''Creates a new segment with the given values.'''
        self.name = name
        self.args = args
        self._process_labels(contents, auto_labels)

    def get_name(self):
        '''Returns the name of the segment.'''
        return self.name

    def get_flags(self):
        '''Returns the flags for the segment.'''
        flags = 0
        for c in self.args.get('segment_flags', 'r'):
            if c == 'r':
                flags |= 0x4
            elif c == 'w':
                flags |= 0x2
            elif c == 'x':
                flags |= 0x1
        return flags

    def get_align(self, default):
        '''Returns the alignment for the segment.'''
        return self.args.get('segment_align', default)

    def get_file_size(self):
        '''Returns the size of the segment in the file.'''
        return self.file_size

    def get_size(self):
        '''Returns the size of the segment in memory.'''
        return max(self.size, self.args.get('segment_size', 0))

    def set_location(self, location_in_file, location_in_memory):
        '''Sets the location of the segment.'''
        self.location_in_file = location_in_file
        self.location_in_memory = location_in_memory

    def render(self, all_labels, endianness):
        '''Returns the binary representation of the segment.'''
        output = b''
        for element in self.contents:
            if type(element) == AbsoluteReference:
                output += element.render(all_labels, endianness)
            elif type(element) == RelativeReference:
                output += element.render(self.labels, endianness)
            elif type(element) == Number:
                output += element.render(endianness)
            else:
                output += element.render()
        return output

    def _process_labels(self, contents, auto_labels):
        self.contents = []
        self.labels = {}
        self.size = 0
        for element in contents:
            if type(element) == Label:
                self._register_label(element)
            else:
                if type(element) == RelativeReference:
                    element.set_location_in_segment(self.size)
                elif type(element) == AbsoluteReference:
                    element.set_own_segment(self.name)
                self.size += element.get_size()
                self.contents.append(element)
        self.file_size = self.size
        for label in auto_labels:
            self._register_label(label)
            self.size += label.get_width()

    def _register_label(self, label):
        if label.name in self.labels:
            raise ElfhexError(
                f'Label {label.name} defined more than once.')
        self.labels[label.name] = label
        label.set_location_in_segment(self.size)


class Label:
    '''A label, which refers to a location.'''

    def __init__(self, name):
        '''Creates a new label with the given name.'''
        self.name = name
        self.location_in_segment = None
        self.absolute_location = None

    def set_location_in_segment(self, location_in_segment):
        '''Sets the location of the label in the segment.'''
        self.location_in_segment = location_in_segment

    def get_location_in_segment(self):
        '''Returns the location in memory of the label in the segment.'''
        return self.location_in_segment

    def set_absolute_location(self, segment_memory_start):
        '''
        Sets the absolute location in memory of the label, based on the location of the start of
        its segment.
        '''
        self.absolute_location = segment_memory_start + self.get_location_in_segment()

    def get_absolute_location(self):
        '''Returns the absolute location in memory of the label.'''
        return self.absolute_location

    def get_size(self):
        '''Returns the size of the label (0 bytes).'''
        return 0


class AutoLabel(Label):
    '''A label whose location is automatically determined.'''

    def __init__(self, name, width):
        '''
        Creates a new auto label with the given name and width. The width represents the number of
        bytes after this label before other content can appear.
        '''
        self.width = width
        super().__init__(name)

    def get_width(self):
        '''Returns the width of the label.'''
        return self.width


class AbsoluteReference:
    '''An absolute reference to a label.'''

    def __init__(self, label, offset, segment=None):
        '''Creates a new absolute reference to the provided label (plus offset).'''
        self.label = label
        self.segment = segment
        self.offset = offset

    def set_own_segment(self, segment):
        '''Sets the segment of the label the reference refers to.'''
        if self.segment is None:
            self.segment = segment

    def get_size(self):
        '''Returns the size of the reference (4 bytes).'''
        return 4

    def render(self, all_labels, endianness):
        '''
        Returns the binary representation of the absolute reference using the provided
        dictionary of labels.
        '''
        if self.label not in all_labels[self.segment]:
            raise ElfhexError(
                f'Absolute reference to non-existent label {self.segment}:{self.label}.')
        return struct.pack(
            f'{endianness}i', all_labels[self.segment][self.label].absolute_location + self.offset)


class RelativeReference:
    '''A relative reference to a label, rendered as the offset from that label.'''

    def __init__(self, label, width=1):
        '''Creates a new relative reference to the provided label, of the given width.'''
        self.label = label
        self.width = width
        self.location_in_segment = None

    def get_size(self):
        '''Returns the width of the relative reference.'''
        return self.width

    def set_location_in_segment(self, location_in_segment):
        '''Sets the location of the relative reference.'''
        self.location_in_segment = location_in_segment

    def get_location_in_segment(self):
        '''Returns the location of the relative reference.'''
        return self.location_in_segment

    def render(self, labels, endianness):
        '''
        Returns the binary representation of the relative reference, given a dictionary of labels
        in its segment.
        '''
        difference = labels[self.label].get_location_in_segment() - \
            self.location_in_segment - self.get_size()
        return struct.pack(f'{endianness}{WIDTH_SYMBOLS[self.get_size()]}', difference)


class Byte:
    '''A byte literal.'''

    def __init__(self, byte):
        '''Creates a new byte.'''
        self.byte = byte

    def get_size(self):
        '''Returns the size of a byte (one byte).'''
        return 1

    def render(self):
        '''Returns the binary representation of the byte.'''
        return bytearray(struct.pack('B', self.byte))


class Number:
    '''A numeric literal of some width.'''

    def __init__(self, number, width, signed):
        '''
        Creates a new number with the given width (padding). If signed is true, then signed
        conversion will occur during rendering.
        '''
        self.number = number
        self.width = width
        self.signed = signed

    def get_size(self):
        '''Returns the width (padded) of the number.'''
        return self.width

    def render(self, endianness):
        '''
        Returns the binary representation of the number. If the number is too large for the width,
        an ElfhexError is raised.
        '''
        width_symbol = WIDTH_SYMBOLS[int(self.width)]
        if self.signed:
            width_symbol = width_symbol.upper()
        try:
            return struct.pack(
                f'{endianness}{width_symbol}', self.number)
        except struct.error:
            raise ElfhexError('Number too big for specified width.')


class String:
    '''A string literal. Only ASCII characters are supported.'''

    def __init__(self, string):
        '''Creates a new string.'''
        self.string = string.encode('ascii')

    def get_size(self):
        '''Returns the length of the string.'''
        return len(self.string)

    def render(self):
        '''Returns the encoded value of the string.'''
        return self.string
