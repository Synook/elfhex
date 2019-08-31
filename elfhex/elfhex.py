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

import struct
from lark import Transformer
from .program import Program, Segment, Label, AbsoluteReference, RelativeReference, Byte, AutoLabel
from .util import WIDTH_SYMBOLS, defaults, ElfhexError


class Elfhex(Transformer):
    def __init__(self, args):
        self.args = args

    def program(self, items):
        return Program(items, self.args)

    def segment(self, items):
        return Segment(self.args, *items)

    def segment_content(self, items):
        return items

    def auto_labels(self, items):
        return items

    def auto_label(self, items):
        name, width = items
        return AutoLabel(name, int(width))

    def segment_args(self, items):
        args = {}
        for item in items:
            value, = item.children
            if value.type in ('POWER_OF_TWO', 'INT'):
                value = int(str(value))
            elif value.type == 'STRING':
                value = value[1:-1]
            elif item.data == 'segment_flags':
                value = str(value)
            args[item.data] = value
        return args

    def label(self, items):
        return Label(*items)

    def abs(self, items):
        (segment, label), offset = defaults(items, 2, 0)
        return AbsoluteReference(label, int(offset), segment)

    def abs_label(self, items):
        if len(items) == 2:
            return items
        else:
            label, = items
            return (None, label)

    def rel(self, items):
        name, width = defaults(items, 2, 1)
        return RelativeReference(str(name), int(width))

    def hex(self, hexdigits):
        return [Byte(int(*hexdigits, 16))]

    def number(self, items):
        sign, number_value = items
        number, base, width = self._parse_number_value(number_value)
        width_symbol = WIDTH_SYMBOLS[int(width)]
        if sign == '=':
            width_symbol = width_symbol.upper()
        try:
            return [
                Byte(a)
                for a in struct.pack(
                    f'{self.args.endianness}{width_symbol}',
                    int(number, base) * (-1 if sign == '-' else 1))]
        except struct.error:
            raise ElfhexError('Number too big for specified width.')

    def _parse_number_value(self, value):
        try:
            width = int(value[-1])
            num, base = value[:-2], value[-2]
        except ValueError:
            width = 1
            num, base = value[:-1], value[-1]
        if base == 'b':
            base = 2
        elif base == 'h':
            base = 16
        else:
            base = 10
        return (num, base, width)

    def label_offset(self, items):
        sign, disp = items
        return int(sign + disp)

    def string(self, string):
        return list(map(lambda c: Byte(ord(c)), string[0][1:-1]))

    def include(self, items):
        return None

    def fragment(self, items):
        return None

    def fragment_var(self, items):
        raise ElfhexError(
            f'Fragment variable reference ${items[0]} found in segment.')
