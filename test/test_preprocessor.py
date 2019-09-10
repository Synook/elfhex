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

import pytest
import elfhex
from .util import MAIN_FILE

METADATA = "program 3 < 16 "


def _segment(content):
    return "segment a() {" + content + " }"


def _flattened(content, metadata=METADATA):
    return elfhex.get_parser().parse(metadata + _segment(content))


def test_preprocessor_includes():
    files = {
        MAIN_FILE: f'{METADATA} include "other.eh" {_segment("ff @f()")}',
        "other.eh": METADATA + "segment a() { ee } fragment f() { 11 }",
    }

    output = elfhex.Preprocessor(files).preprocess(MAIN_FILE, 2)

    assert output == _flattened("ff 11 ee")


def test_preprocessor_fragmentsonly():
    files = {
        MAIN_FILE: f'{METADATA} include fragments "other.eh" {_segment("ff @f()")}',
        "other.eh": METADATA + "segment a() { ee } fragment f() { 11 }",
    }

    output = elfhex.Preprocessor(files).preprocess(MAIN_FILE, 2)

    assert output == _flattened("ff 11")


def test_preprocessor_includeonce():
    files = {
        MAIN_FILE: f'{METADATA} include "other.eh" {_segment("")}',
        "other.eh": f'{METADATA} include "{MAIN_FILE}"',
    }

    elfhex.Preprocessor(files).preprocess(MAIN_FILE, 2)

    # should not recursively loop includes


def test_preprocessor_fragments():
    files = {
        MAIN_FILE: METADATA
        + _segment("ff @a(11)")
        + "fragment a(a) { $a @b($a) } fragment b(a) { $a }"
    }

    output = elfhex.Preprocessor(files).preprocess(MAIN_FILE, 3)

    assert output == _flattened("ff 11 11")


def test_preprocessor_maxrecursion():
    files = {
        MAIN_FILE: METADATA
        + _segment("@a()")
        + " fragment a() { @b() } fragment b() { @c() } fragment c() { ff }"
    }

    with pytest.raises(elfhex.ElfhexError):
        elfhex.Preprocessor(files).preprocess(MAIN_FILE, 0)


def test_preprocessor_aliases():
    files = {MAIN_FILE: METADATA + _segment("@a()(test)") + " fragment a() { [a] }"}

    output = elfhex.Preprocessor(files).preprocess(MAIN_FILE, 2)

    assert output == _flattened("[test.a]")


def test_preprocessor_locallabels():
    files = {MAIN_FILE: METADATA + _segment("@a()") + " fragment a() { [__a] }"}

    output = elfhex.Preprocessor(files).preprocess(MAIN_FILE, 2)

    assert output == _flattened("[__0__a]")


def test_preprocessor_uniqueref():
    files = {
        MAIN_FILE: METADATA + _segment("@!a() @!a() @a()") + " fragment a() { 00 }"
    }

    output = elfhex.Preprocessor(files).preprocess(MAIN_FILE, 2)

    assert output == _flattened("00 00")


def test_preprocessor_wrongarglen():
    files = {MAIN_FILE: METADATA + _segment("@!a(11)") + " fragment a() { 00 }"}

    with pytest.raises(elfhex.ElfhexError):
        elfhex.Preprocessor(files).preprocess(MAIN_FILE, 2)


def test_preprocessor_nofragment():
    files = {MAIN_FILE: METADATA + _segment("@!b()") + " fragment a() { 00 }"}

    with pytest.raises(elfhex.ElfhexError):
        elfhex.Preprocessor(files).preprocess(MAIN_FILE, 2)


def test_preprocessor_invalidfragmentdepth():
    with pytest.raises(ValueError):
        elfhex.Preprocessor({}).preprocess(MAIN_FILE, -1)


def test_preprocessor_incompatiblemetadata():
    files = {
        MAIN_FILE: 'program 3 < 4096 include "other.eh" ' + _segment(""),
        "other.eh": "program 2 < 4096",
    }

    with pytest.raises(elfhex.ElfhexError):
        elfhex.Preprocessor(files).preprocess(MAIN_FILE, 1)

    files = {
        MAIN_FILE: 'program 3 < 4096 include "other.eh" ' + _segment(""),
        "other.eh": "program 3 > 4096",
    }

    with pytest.raises(elfhex.ElfhexError):
        elfhex.Preprocessor(files).preprocess(MAIN_FILE, 1)


def test_preprocessor_extendalign():
    files = {
        MAIN_FILE: 'program 3 < 16 include "other.eh" ' + _segment(""),
        "other.eh": "program 3 < 32",
    }

    output = elfhex.Preprocessor(files).preprocess(MAIN_FILE, 1)

    assert output == _flattened("", metadata="program 3 < 32")
