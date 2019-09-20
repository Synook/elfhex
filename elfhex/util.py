#!/usr/bin/python
#
# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0,
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""This module contains utility functions and classes."""

import os
import lark
import inspect

_WIDTH_SYMBOLS = {1: "b", 2: "h", 4: "i", 8: "q"}


class ElfhexError(Exception):
    """An error encountered while assembling an ELFHex program."""


def width_symbol(width, signed):
    symbol = _WIDTH_SYMBOLS[width]
    return symbol.lower() if signed else symbol.upper()


def get_parser():
    """Returns a parser for the ELFHex input language."""
    grammar_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "elfhex.lark"
    )
    return lark.Lark(open(grammar_path).read(), parser="lalr", start="program")


def defaults(items, expected, *default_values):
    """Pads the items list up to the expected length with the provided defaults."""
    if len(items) == expected:
        return items
    if len(items) + len(default_values) < expected:
        raise Exception("Too few items, even with defaults.")
    items = list(items)
    items.extend(default_values[len(items) - expected - 1 :])
    return items


def call_with_args(element, method_name, program, segment):
    """Calls the given method, optionally with the program and segment arguments set
    if they exist as parameters on the method.
    """
    method = getattr(element, method_name)
    params = inspect.signature(method).parameters
    args = {}
    if "program" in params:
        args["program"] = program
    if "segment" in params:
        args["segment"] = segment
    return method(**args)
