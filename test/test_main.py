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

import elfhex.__main__ as main
from .util import StandardArgs, FakeFileLoader, GRAMMAR, MAIN_FILE


@pytest.fixture
def fake_file_loader():
    return FakeFileLoader()


def _start_segment(b):
    return 'segment a() { [_start] ' + b + ' }'


def test_assemble_output(fake_file_loader):
    fake_file_loader.add_file(
        MAIN_FILE, _start_segment('ff ee # comment \n'))

    output = main.assemble(StandardArgs(), GRAMMAR, fake_file_loader)

    assert output == b'\xff\xee'


def test_assemble_relativeref(fake_file_loader):
    fake_file_loader.add_file(
        MAIN_FILE, _start_segment('[test] 00 <test>'))

    output = main.assemble(StandardArgs(), GRAMMAR, fake_file_loader)

    assert output == b'\x00\xfe'


def test_assemble_relativeref_width(fake_file_loader):
    fake_file_loader.add_file(
        MAIN_FILE, _start_segment('[test] 00 <test:4>'))

    output = main.assemble(StandardArgs(), GRAMMAR, fake_file_loader)

    assert output == b'\x00\xfb\xff\xff\xff'


def test_assemble_absoluteref(fake_file_loader):
    fake_file_loader.add_file(
        MAIN_FILE, _start_segment('11 [test] 00 <<test>>'))
    args = StandardArgs()

    output = main.assemble(args, GRAMMAR, fake_file_loader)

    label_location = struct.pack(
        f'{args.endianness}I', args.memory_start + 1)
    assert output == b'\x11\x00' + label_location


def test_assemble_numberliterals(fake_file_loader):
    fake_file_loader.add_file(
        MAIN_FILE, _start_segment('11 =11111111b =16d2 =aah4 00'))

    output = main.assemble(StandardArgs(), GRAMMAR, fake_file_loader)

    assert output == b'\x11\xff\x10\x00\xaa\x00\x00\x00\x00'


def test_assemble_stringliterals(fake_file_loader):
    string = "test"
    fake_file_loader.add_file(
        MAIN_FILE, _start_segment(f'11 \"{string}\" 00'))

    output = main.assemble(StandardArgs(), GRAMMAR, fake_file_loader)

    assert output == b'\x11' + string.encode('ascii') + b'\x00'


def test_assemble_fragments(fake_file_loader):
    fake_file_loader.add_file(
        MAIN_FILE, f'''
{_start_segment(f'11 @f1(ff) 00')}
fragment f1(a) {{ @f2(ee $a) }}
fragment f2(b) {{ dd $b }}
''')

    output = main.assemble(StandardArgs(), GRAMMAR, fake_file_loader)

    assert output == b'\x11\xdd\xee\xff\x00'


def test_assemble_includes(fake_file_loader):
    fake_file_loader.add_file(
        MAIN_FILE, f'''
include "other.eh"
{_start_segment(f'ff @f()')}
''')
    fake_file_loader.add_file('other.eh', '''
segment a() { ee }
fragment f() { 11 }
''')

    output = main.assemble(StandardArgs(), GRAMMAR, fake_file_loader)

    assert output == b'\xff\x11\xee'


def test_assemble_autolabels(fake_file_loader):
    fake_file_loader.add_file(
        MAIN_FILE, _start_segment('ff <l> <l2> [[l: 4 l2: 8]]'))

    output = main.assemble(StandardArgs(), GRAMMAR, fake_file_loader)

    assert output == b'\xff\x01\x04'
