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

"""
This module contains the main components of an ELFHex program. These are used to
constuct a Program instance when the source file's syntax tree is processed in the
Transformer. The program instance consists of Segments, which then contain other
elements. All children of segments should support the get_size() and render()
methods.
"""

import collections
import struct
import math
import importlib
from . import util


class Program:
    """The representation of an ELFHex program, which consists of segments."""

    def __init__(self, metadata, segments):
        """Create a new program with the provided metadata and segment list."""
        self.segments = collections.OrderedDict(
            (segment.name, segment) for segment in segments
        )
        self.metadata = metadata

    def get_segments(self):
        """Returns the segments in the program."""
        return self.segments

    def get_metadata(self):
        """Returns the program metadata."""
        return self.metadata

    def get_label_location(self, label, segment=None):
        """Returns the memory location of a label. Can only be used during/after calling
        render, for example in the render method of program components such as
        references.
        """
        if segment:
            if (
                segment in self.segments
                and label in self.segments[segment].get_labels()
            ):
                return self.segments[segment].get_labels()[label].absolute_location
            raise util.ElfhexError(f"Label [{segment}:{label}] not defined.")
        for program_segment in self.segments.values():
            if label in program_segment.get_labels():
                return program_segment.get_labels()[label].absolute_location
        raise util.ElfhexError(f"Label [{label}] not found in any segment.")

    def prepend_header_segment(self, header):
        """Adds a new header segment at the start with the specified content."""
        segment = Segment("__header__", {}, header)
        new_segments = collections.OrderedDict()
        new_segments[segment.name] = segment
        for key, value in self.segments.items():
            new_segments[key] = value
        self.segments = new_segments

    def prepend_header_to_first_segment(self, header):
        """Prepends the given header content to the first segment."""
        target = list(self.segments.values())[0]
        target.prepend_content(header)

    def render(self, memory_start):
        """Returns the binary representation of the program."""
        self._set_label_locations(memory_start)
        return b"".join(segment.render(self) for segment in self.segments.values())

    def _set_label_locations(self, memory_start):
        for segment in self.segments.values():
            segment.process_labels(self)
        location_in_file = 0
        location_in_memory = memory_start + self._shift_to_align(0, self.metadata.align)
        for segment in self.segments.values():
            # ensures segment is properly aligned in memory
            position_shift = location_in_file % segment.get_align(self.metadata.align)
            location_in_memory += position_shift - (
                location_in_memory % segment.get_align(self.metadata.align)
            )
            segment.set_location(location_in_file, location_in_memory)

            for label in segment.labels.values():
                label.set_absolute_location(location_in_memory)

            location_in_file += segment.get_file_size()
            location_in_memory += self._shift_to_align(
                segment.get_size(), self.metadata.align
            )

    @staticmethod
    def _shift_to_align(size, alignment):
        return math.ceil(size / alignment) * alignment


Metadata = collections.namedtuple("Metadata", ["machine", "endianness", "align"])


class Segment:
    """A segment in an ELFHex program."""

    def __init__(self, name, args, contents, auto_labels=()):
        """Creates a new segment with the given values."""
        self.name = name
        self.args = args
        self.auto_labels = auto_labels
        self.contents = contents
        self.labels = {}
        self.location_in_file = 0
        self.location_in_memory = 0
        self.size = 0
        self.file_size = 0

    def get_name(self):
        """Returns the name of the segment."""
        return self.name

    def get_flags(self):
        """Returns the flags for the segment."""
        flags = 0
        for char in self.args.get("segment_flags", "r"):
            if char == "r":
                flags |= 0x4
            elif char == "w":
                flags |= 0x2
            elif char == "x":
                flags |= 0x1
        return flags

    def get_align(self, default):
        """Returns the alignment for the segment."""
        return self.args.get("segment_align", default)

    def get_file_size(self):
        """Returns the size of the segment in the file."""
        return self.file_size

    def get_size(self):
        """Returns the size of the segment in memory."""
        return max(self.size, self.args.get("segment_size", 0))

    def set_location(self, location_in_file, location_in_memory):
        """Sets the location of the segment."""
        self.location_in_file = location_in_file
        self.location_in_memory = location_in_memory

    def prepend_content(self, content):
        """Adds the provided content to the start of the segment."""
        self.contents = content + self.contents

    def render(self, program):
        """Returns the binary representation of the segment."""
        return b"".join(
            util.call_with_args(element, "render", program, self)
            for element in self.contents
        )

    def get_labels(self):
        """Returns the labels in the segment."""
        return self.labels

    def process_labels(self, program):
        """Determines the location of elements in the segment. Called during the
        rendering process.
        """
        self.labels = {}
        self.size = 0
        for element in self.contents:
            if isinstance(element, Label):
                self._register_label(element)
            if isinstance(element, RelativeReference):
                element.set_location_in_segment(self.size)
            if isinstance(element, AbsoluteReference):
                element.set_own_segment(self.name)
            self.size += util.call_with_args(element, "get_size", program, self)
        self.file_size = self.size
        for label in self.auto_labels:
            self._register_label(label)
            self.size += label.get_width()

    def _register_label(self, label):
        if label.name in self.labels:
            raise util.ElfhexError(f"Label {label.name} defined more than once.")
        self.labels[label.name] = label
        label.set_location_in_segment(self.size)


class Label:
    """A label, which refers to a location in memory."""

    def __init__(self, name):
        """Creates a new label with the given name."""
        self.name = name
        self.location_in_segment = 0
        self.absolute_location = 0

    def set_location_in_segment(self, location_in_segment):
        """Sets the location of the label in the segment."""
        self.location_in_segment = location_in_segment

    def get_location_in_segment(self):
        """Returns the location in memory of the label in the segment."""
        return self.location_in_segment

    def set_absolute_location(self, segment_memory_start):
        """Sets the absolute location in memory of the label, based on the location of
        the start of its segment.
        """
        self.absolute_location = segment_memory_start + self.get_location_in_segment()

    def get_absolute_location(self):
        """Returns the absolute location in memory of the label."""
        return self.absolute_location

    @staticmethod
    def get_size():
        """Returns the size of the label (0 bytes)."""
        return 0

    @staticmethod
    def render():
        """Returns the binary representation of the label (an empty byte-string; labels
        themselves do not appear in the output).
        """
        return b""


class AutoLabel(Label):
    """A label whose location is automatically determined."""

    def __init__(self, name, width):
        """Creates a new auto label with the given name and width. The width represents
        the number of bytes after this label before other content can appear.
        """
        self.width = width
        super().__init__(name)

    def get_width(self):
        """Returns the width of the label."""
        return self.width


class AbsoluteReference:
    """An absolute reference to a label."""

    def __init__(self, label, offset, segment=None):
        """Creates a new absolute reference to the provided label (plus offset)."""
        self.label = label
        self.segment = segment
        self.offset = offset

    def set_own_segment(self, segment):
        """Sets the segment of the label the reference refers to."""
        if self.segment is None:
            self.segment = segment

    @staticmethod
    def get_size():
        """Returns the size of the reference (4 bytes)."""
        return 4

    def render(self, program):
        """Returns the binary representation of the absolute reference."""
        return struct.pack(
            f"{program.get_metadata().endianness}I",
            program.get_label_location(self.label, self.segment) + self.offset,
        )


class RelativeReference:
    """A relative reference to a label, rendered as the offset from that label."""

    def __init__(self, label, width=1):
        """Creates a new relative reference to the provided label, of the given width.
        """
        self.label = label
        self.width = width
        self.location_in_segment = None

    def get_size(self):
        """Returns the width of the relative reference."""
        return self.width

    def set_location_in_segment(self, location_in_segment):
        """Sets the location of the relative reference."""
        self.location_in_segment = location_in_segment

    def get_location_in_segment(self):
        """Returns the location of the relative reference."""
        return self.location_in_segment

    def render(self, program, segment):
        """
        Returns the binary representation of the relative reference.
        """
        difference = (
            segment.get_labels()[self.label].get_location_in_segment()
            - self.location_in_segment
            - self.get_size()
        )
        return struct.pack(
            program.get_metadata().endianness
            + util.width_symbol(self.get_size(), True),
            difference,
        )


class Byte:
    """A byte literal."""

    def __init__(self, byte):
        """Creates a new byte."""
        self.byte = byte

    @staticmethod
    def get_size():
        """Returns the size of a byte (one byte)."""
        return 1

    def render(self):
        """Returns the binary representation of the byte."""
        return bytearray(struct.pack("B", self.byte))


class Number:
    """A numeric literal of some width."""

    def __init__(self, number, width=1, signed=False):
        """Creates a new number with the given width (padding). If signed is true, then
        signed conversion will occur during rendering.
        """
        self.number = number
        self.width = width
        self.signed = signed

    def get_size(self):
        """Returns the width (padded) of the number."""
        return self.width

    def render(self, program):
        """Returns the binary representation of the number. If the number is too large
        for the width, an ElfhexError is raised.
        """
        try:
            return struct.pack(
                program.get_metadata().endianness
                + util.width_symbol(self.width, self.signed),
                self.number,
            )
        except struct.error:
            raise util.ElfhexError("Number too big for specified width.")


class String:
    """A string literal. Only ASCII characters are supported."""

    def __init__(self, string):
        """Creates a new string."""
        self.string = string.encode("ascii")

    def get_size(self):
        """Returns the length of the string."""
        return len(self.string)

    def render(self):
        """Returns the encoded value of the string."""
        return self.string


class Extension:
    def __init__(self, name, content, absolute):
        if not absolute:
            name = f"elfhex.extensions.{name}"
        extension = importlib.import_module(name)
        self.value = extension.parse(content)

    def get_size(self, program, segment):
        return util.call_with_args(self.value, "get_size", program, segment)

    def render(self, program, segment):
        return util.call_with_args(self.value, "render", program, segment)
