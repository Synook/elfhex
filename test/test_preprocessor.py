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


def _start_segment(content):
    return 'segment a() { [_start] ' + content + ' }'


def _flattened(content):
    return elfhex.Preprocessor(
        {MAIN_FILE: (_start_segment(content), MAIN_FILE)}).preprocess(MAIN_FILE, 1)


def test_preprocessor_includes():
    files = {
        MAIN_FILE: (
            f'include "other.eh" {_start_segment("ff @f()")}',
            MAIN_FILE),
        'other.eh': (
            'segment a() { ee } fragment f() { 11 }',
            'other.eh')}

    output = elfhex.Preprocessor(files).preprocess(MAIN_FILE, 2)

    assert output == _flattened('ff 11 ee')


def test_preprocessor_fragmentsonly():
    files = {
        MAIN_FILE: (
            f'include fragments "other.eh" {_start_segment("ff @f()")}',
            MAIN_FILE),
        'other.eh': (
            'segment a() { ee } fragment f() { 11 }',
            'other.eh')}

    output = elfhex.Preprocessor(files).preprocess(MAIN_FILE, 2)

    assert output == _flattened('ff 11')


def test_preprocessor_includeonce():
    files = {
        MAIN_FILE: (
            f'include "other.eh" {_start_segment("")}',
            MAIN_FILE),
        'other.eh': (
            f'include "{MAIN_FILE}"',
            'other.eh')}

    elfhex.Preprocessor(files).preprocess(MAIN_FILE, 2)

    # should not recursively loop includes


def test_preprocessor_fragments():
    files = {
        MAIN_FILE: (
            _start_segment("ff @a(11)") +
            ' fragment a(a) { $a @b($a) } fragment b(a) { $a }',
            MAIN_FILE)}

    output = elfhex.Preprocessor(files).preprocess(MAIN_FILE, 3)

    assert output == _flattened('ff 11 11')


def test_preprocessor_maxrecursion():
    files = {
        MAIN_FILE: (
            _start_segment("@a()")
            + ' fragment a() { @b() }'
            + ' fragment b() { @c() }'
            + ' fragment c() { ff }',
            MAIN_FILE)}

    with pytest.raises(elfhex.ElfhexError):
        elfhex.Preprocessor(files).preprocess(MAIN_FILE, 0)


def test_preprocessor_aliases():
    files = {
        MAIN_FILE: (
            _start_segment("@a()(test)") + ' fragment a() { [a] }',
            MAIN_FILE)}

    output = elfhex.Preprocessor(files).preprocess(MAIN_FILE, 2)

    assert output == _flattened('[test.a]')


def test_preprocessor_locallabels():
    files = {
        MAIN_FILE: (
            _start_segment("@a()") + ' fragment a() { [__a] }',
            MAIN_FILE)}

    output = elfhex.Preprocessor(files).preprocess(MAIN_FILE, 2)

    assert output == _flattened('[__0__a]')


def test_preprocessor_uniqueref():
    files = {
        MAIN_FILE: (
            _start_segment("@!a() @!a() @a()") + ' fragment a() { 00 }',
            MAIN_FILE)}

    output = elfhex.Preprocessor(files).preprocess(MAIN_FILE, 2)

    assert output == _flattened('00 00')


def test_preprocessor_wrongarglen():
    files = {
        MAIN_FILE: (
            _start_segment("@!a(11)") + ' fragment a() { 00 }',
            MAIN_FILE)}

    with pytest.raises(elfhex.ElfhexError):
        elfhex.Preprocessor(files).preprocess(MAIN_FILE, 2)


def test_preprocessor_nofragment():
    files = {
        MAIN_FILE: (
            _start_segment("@!b()") + ' fragment a() { 00 }',
            MAIN_FILE)}

    with pytest.raises(elfhex.ElfhexError):
        elfhex.Preprocessor(files).preprocess(MAIN_FILE, 2)


def test_preprocessor_invalidfragmentdepth():
    with pytest.raises(ValueError):
        elfhex.Preprocessor({}).preprocess(MAIN_FILE, -1)
