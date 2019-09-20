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

import lark
from . import program, util


class Transformer(lark.Transformer):
    """Transforms a parsed ELFHex syntax tree into an elfhex.program.Program. The syntax
    tree must only contain the program declaration and segments: use elfhex.Preprocessor
    to resolve includes and fragment references.
    """

    def program(self, items):
        return program.Program(items[0], items[1:])

    def metadata(self, items):
        machine, endianness, align = items
        return program.Metadata(
            machine=int(machine), endianness=endianness, align=int(align)
        )

    def segment(self, items):
        name, args, contents, auto_labels = items
        return program.Segment(str(name), args, contents, auto_labels)

    def segment_content(self, items):
        return items

    def auto_labels(self, items):
        return items

    def auto_label(self, items):
        name, width = items
        return program.AutoLabel(str(name), int(width))

    def segment_args(self, items):
        args = {}
        for item in items:
            value, = item.children
            if item.data == "segment_flags":
                value = str(value)
            else:
                value = int(value)
            args[item.data] = value
        return args

    def label(self, items):
        name, = items
        return program.Label(str(name))

    def abs(self, items):
        (segment, label), offset = util.defaults(items, 2, 0)
        return program.AbsoluteReference(label, int(offset), segment)

    def abs_label(self, items):
        if len(items) == 2:
            label, segment = items
            return str(label), str(segment)
        else:
            label, = items
            return (None, str(label))

    def rel(self, items):
        name, width = util.defaults(items, 2, 1)
        return program.RelativeReference(str(name), int(width))

    def hex(self, hexdigits):
        return program.Byte(int(*hexdigits, 16))

    def number(self, items):
        sign, number_value = items
        number, base, width = self._parse_number_value(number_value)
        return program.Number(
            int(number, base) * (-1 if sign == "-" else 1), width, sign != "="
        )

    def _parse_number_value(self, value):
        try:
            width = int(value[-1])
            num, base = value[:-2], value[-2]
        except ValueError:
            width = 1
            num, base = value[:-1], value[-1]
        if base == "b":
            base = 2
        elif base == "h":
            base = 16
        else:
            base = 10
        return (num, base, width)

    def label_offset(self, items):
        sign, disp = items
        return int(sign + disp)

    def string(self, items):
        string, = items
        return program.String(string[1:-1])

    def fragment_var(self, items):
        raise util.ElfhexError(
            f"Fragment variable reference ${items[0]} found in segment."
        )

    def extension(self, items):
        extension_type, name, content = items
        return program.Extension(str(name), content, extension_type == "::")

    def extension_content(self, items):
        content = " ".join(items)
        return str(content)
