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

import os

GRAMMAR = open(os.path.join(os.path.dirname(
    os.path.abspath(__file__)), '..', 'elfhex', 'elfhex.lark')).read()
MAIN_FILE = 'test_input.eh'


class FakeFileLoader:
    def __init__(self):
        self.files = {}

    def add_file(self, path, content):
        self.files[path] = content

    def load(self, path):
        return self.files[path], path


class StandardArgs:
    def __init__(self):
        self.input_path = MAIN_FILE
        self.include_path = ['']
        self.max_fragment_depth = 10
        self.no_header = True
        self.memory_start = 0x1000
        self.default_align = 16
        self.endianness = '<'
        self.machine = 3
        self.entry_label = '_start'
