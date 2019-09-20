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

import enum
import pytest
from lark.exceptions import VisitError
import elfhex
import unittest.mock as mock


class Type(enum.Enum):
    PROGRAM = 1
    SEGMENT = 2
    METADATA = 3
    BYTE = 4
    AUTO_LABEL = 5


@pytest.fixture
def transformer():
    return elfhex.Transformer()


@pytest.fixture(autouse=True)
def mock_program(mocker):
    mock_program = mocker.patch("elfhex.transformer.program", autospec=True)
    mock_program.Program.return_value = Type.PROGRAM
    mock_program.Segment.return_value = Type.SEGMENT
    mock_program.Metadata.return_value = Type.METADATA
    mock_program.Byte.return_value = Type.BYTE
    mock_program.AutoLabel.return_value = Type.AUTO_LABEL
    return mock_program


def _parse(content, name="a", args=""):
    return elfhex.get_parser().parse(
        f"program 3 < 16 segment {name}({args}) {{{content}}}"
    )


def test_transform_segment(transformer, mock_program):
    name = "a"
    parsed = _parse("ff", name=name, args="size: 4 align: 16 flags: rw")

    program = transformer.transform(parsed)

    assert program == Type.PROGRAM
    mock_program.Program.assert_called_once_with(Type.METADATA, [Type.SEGMENT])
    mock_program.Metadata.assert_called_once_with(machine=3, endianness="<", align=16)
    mock_program.Segment.assert_called_once_with(
        name,
        {"segment_size": 4, "segment_align": 16, "segment_flags": "rw"},
        [Type.BYTE],
        [],
    )
    mock_program.Byte.assert_called_once_with(255)


def test_transform_string(transformer, mock_program):
    parsed = _parse('"test"')

    program = transformer.transform(parsed)

    assert program == Type.PROGRAM
    mock_program.String.assert_called_once_with("test")


def test_transform_number(transformer, mock_program):
    parsed = _parse("=10d4 +ah2 -1001b")

    program = transformer.transform(parsed)

    assert program == Type.PROGRAM
    mock_program.Number.assert_has_calls(
        [mock.call(10, 4, False), mock.call(10, 2, True), mock.call(-9, 1, True)]
    )


def test_transform_label(transformer, mock_program):
    parsed = _parse("[label]")

    program = transformer.transform(parsed)

    assert program == Type.PROGRAM
    mock_program.Label.assert_called_once_with("label")


def test_transform_relative_reference(transformer, mock_program):
    parsed = _parse("<a> <b:4>")

    program = transformer.transform(parsed)

    assert program == Type.PROGRAM
    mock_program.RelativeReference.assert_has_calls(
        [mock.call("a", 1), mock.call("b", 4)]
    )


def test_transform_absolute_reference(transformer, mock_program):
    parsed = _parse("<<a>> <<b + 4>> <<s:c - 2>>")

    program = transformer.transform(parsed)

    assert program == Type.PROGRAM
    mock_program.AbsoluteReference.assert_has_calls(
        [mock.call("a", 0, None), mock.call("b", 4, None), mock.call("c", -2, "s")]
    )


def test_transform_autolabel(transformer, mock_program):
    parsed = _parse("00 [[a: 4 b: 8]]")

    program = transformer.transform(parsed)

    assert program == Type.PROGRAM
    mock_program.Segment.assert_called_once_with(
        mock.ANY, mock.ANY, [Type.BYTE], [Type.AUTO_LABEL, Type.AUTO_LABEL]
    )
    mock_program.AutoLabel.assert_has_calls([mock.call("a", 4), mock.call("b", 8)])


def test_transform_fragment_var_error(transformer, mock_program):
    parsed = _parse("$a")

    with pytest.raises(VisitError):
        transformer.transform(parsed)


def test_transform_extension(transformer, mock_program):
    parsed = _parse(":test_ex {content} ::absolute {content2}")

    program = transformer.transform(parsed)

    assert program == Type.PROGRAM
    mock_program.Extension.assert_has_calls(
        [
            mock.call("test_ex", "content", False),
            mock.call("absolute", "content2", True),
        ]
    )
