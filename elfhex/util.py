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

WIDTH_SYMBOLS = {
    1: 'b',
    2: 'h',
    4: 'i',
    8: 'q'
}


class ElfhexError(Exception):
    pass


def defaults(items, expected, *defaults):
    if len(items) == expected:
        return items
    if len(items) + len(defaults) < expected:
        raise Exception('Too few items, even with defaults.')
    items = list(items)
    items.extend(defaults[len(items) - expected - 1:])
    return items
