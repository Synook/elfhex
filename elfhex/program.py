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
    def __init__(self, metadata, segments):
        self.segments = [(segment.name, segment)
                         for segment in segments if segment]
        self.metadata = metadata
        self.label_locations_set = False

    def get_segments(self):
        return self.segments

    def get_segment_count(self):
        return len(self.segments)

    def get_metadata(self):
        return self.metadata

    def get_label_location(self, label_name):
        self._check_label_locations_set()
        for _, segment in self.segments:
            for _, label in segment.labels.items():
                if label.name == label_name:
                    return label.absolute_location
        raise ElfhexError(
            f'Label [{label_name}] not defined.')

    def get_memory_start(self):
        self._check_label_locations_set()
        return self.memory_start

    def _shift_to_align(self, n, alignment):
        return math.ceil(n / alignment) * alignment

    def set_label_locations(self, header_size, memory_start):
        self.label_locations_set = True
        self.memory_start = memory_start
        # leave space for header in memory
        location_in_file = header_size
        memory_start += self._shift_to_align(header_size, self.metadata.align)
        for _, segment in self.segments:
            segment.set_location_in_file(location_in_file)

            position_shift = location_in_file % segment.get_align(
                self.metadata.align)
            memory_start += position_shift - \
                (memory_start % segment.get_align(self.metadata.align))
            segment.set_location_in_memory(memory_start)

            for label in segment.labels.values():
                label.set_absolute_location(memory_start)

            location_in_file += segment.get_file_size()
            memory_start += self._shift_to_align(
                segment.get_size(), self.metadata.align)

    def render(self):
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


Metadata = collections.namedtuple(
    'Metadata',
    ['machine', 'endianness', 'align']
)


class Segment:
    def __init__(self, name, args, contents, auto_labels):
        self.name = name
        self.args = args
        self._process_labels(contents, auto_labels)

    def get_name(self):
        return self.name

    def get_flags(self):
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
        return self.args.get('segment_align', default)

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

    def set_location_in_memory(self, location_in_memory):
        self.location_in_memory = location_in_memory

    def set_location_in_file(self, location_in_file):
        self.location_in_file = location_in_file

    def render(self, all_labels, endianness):
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

    def get_file_size(self):
        return self.file_size

    def get_size(self):
        return max(self.size, self.args.get('segment_size', 0))


class Label:
    def __init__(self, name):
        self.name = name
        self.location_in_segment = None
        self.absolute_location = None

    def set_location_in_segment(self, location_in_segment):
        self.location_in_segment = location_in_segment

    def get_location_in_segment(self):
        return self.location_in_segment

    def set_absolute_location(self, segment_memory_start):
        self.absolute_location = segment_memory_start + self.get_location_in_segment()

    def get_absolute_location(self):
        return self.absolute_location

    def get_size(self):
        return 0


class AutoLabel(Label):
    def __init__(self, name, width):
        self.width = width
        super().__init__(name)

    def get_width(self):
        return self.width


class AbsoluteReference:
    def __init__(self, label, offset, segment=None):
        self.label = label
        self.segment = segment
        self.offset = offset

    def set_own_segment(self, segment):
        if self.segment is None:
            self.segment = segment

    def get_size(self):
        return 4

    def render(self, all_labels, endianness):
        if self.label not in all_labels[self.segment]:
            raise ElfhexError(
                f'Absolute reference to non-existent label {self.segment}:{self.label}.')
        return struct.pack(f'{endianness}i', all_labels[self.segment][self.label].absolute_location + self.offset)


class RelativeReference:
    def __init__(self, label, width=1):
        self.label = label
        self.width = width
        self.location_in_segment = None

    def get_size(self):
        return self.width

    def set_location_in_segment(self, location_in_segment):
        self.location_in_segment = location_in_segment

    def get_location_in_segment(self):
        return self.location_in_segment

    def render(self, labels, endianness):
        difference = labels[self.label].get_location_in_segment() - \
            self.location_in_segment - self.get_size()
        return struct.pack(f'{endianness}{WIDTH_SYMBOLS[self.get_size()]}', difference)


class Byte:
    def __init__(self, byte):
        self.byte = byte

    def get_size(self):
        return 1

    def render(self):
        return bytearray(struct.pack('B', self.byte))


class Number:
    def __init__(self, number, width, signed):
        self.number = number
        self.width = width
        self.signed = signed

    def get_size(self):
        return self.width

    def render(self, endianness):
        width_symbol = WIDTH_SYMBOLS[int(self.width)]
        if self.signed:
            width_symbol = width_symbol.upper()
        try:
            return struct.pack(
                f'{endianness}{width_symbol}', self.number)
        except struct.error:
            raise ElfhexError('Number too big for specified width.')


class String:
    def __init__(self, string):
        self.string = string.encode('ascii')

    def get_size(self):
        return len(self.string)

    def render(self):
        return self.string
