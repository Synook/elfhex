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
import pytest
from lark.exceptions import VisitError
from elfhex.extensions.x86.args import parse


def test_parse_reg():
    output = parse("ecx, esi").render(None, None)

    assert output == b"\xce"


def test_parse_number():
    output = parse("1, esi").render(None, None)

    assert output == b"\xce"


def test_parse_alias():
    output = parse("cl, dh").render(None, None)

    assert output == b"\xce"


def test_parse_base():
    output = parse("ecx, [esi]").render(None, None)

    assert output == b"\x0e"


def test_parse_base_disp():
    output = parse("ecx, [esi + 8]").render(None, None)

    assert output == b"\x4e\x08"


def test_parse_base_disp32():
    output = parse("ecx, [esi + 800]").render(None, None)

    assert output == b"\x8e\x20\x03\x00\x00"


def test_parse_base_index():
    output = parse("ecx, [esi + ebx]").render(None, None)

    assert output == b"\x0c\x1e"


def test_parse_base_index_scale():
    output = parse("ecx, [esi + ebx * 2]").render(None, None)

    assert output == b"\x0c\x5e"


def test_parse_index():
    output = parse("ecx, [esi * 8]").render(None, None)

    assert output == b"\x0c\xf5\x00\x00\x00\x00"


def test_parse_index_disp():
    output = parse("ecx, [esi * 8 - 4]").render(None, None)

    assert output == b"\x0c\xF5\xfc\xff\xff\xff"


def test_parse_base_index_disp():
    output = parse("ecx, [esi + ebx - aah]").render(None, None)

    assert output == b"\x8c\x1e\x56\xff\xff\xff"


def test_parse_base_index_scale_disp():
    output = parse("ecx, [esi + ebx * 4 - aah]").render(None, None)

    assert output == b"\x8c\x9e\x56\xff\xff\xff"


def test_parse_esp():
    # esp is a special case
    output = parse("ecx, [esp + eh]").render(None, None)

    assert output == b"\x4c\x24\x0e"


def test_parse_ebp():
    # ebp is also a special case
    output = parse("ecx, [ebp]").render(None, None)

    assert output == b"\x4d\x00"


def test_parse_pointer():
    segment_name = "segment"
    label_name = "label"
    memory_location = 19

    class Segment:
        def get_name(self):
            return segment_name

    class Program:
        def get_label_location(self, label, segment):
            assert segment == segment_name
            assert label == label_name
            return memory_location

    output = parse(f"ecx, [ebx + dword ptr {label_name}]").render(Program(), Segment())

    assert output == b"\x8b" + struct.pack("<I", memory_location)


def test_parse_esp_index():
    with pytest.raises(VisitError):
        parse("ecx, [esp * 4]").render(None, None)
