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
import pytest
import uuid
import tempfile
import platform
import subprocess
import stat
import elfhex.__main__ as main


@pytest.fixture
def include_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _create_output_path():
    return os.path.join(tempfile.gettempdir(), f"elfhex_test_output_{uuid.uuid1().hex}")


def _assert_execution_output(binary_path, output):
    if platform.system() == "Linux":
        os.chmod(binary_path, stat.S_IRUSR | stat.S_IWRITE | stat.S_IXUSR)
        output = subprocess.check_output([binary_path])
        assert output == b"aaaaa"


def test_assemble(include_path):
    output_path = _create_output_path()

    main.assemble(["-i", include_path, "test.eh", output_path])

    content = open(output_path, "rb").read()
    assert content[0:4] == b"\x7fELF"

    # if we are on Linux, we try to actually run our program.
    _assert_execution_output(output_path, b"aaaaa")

    os.remove(output_path)


def test_assemble_header_segment(include_path):
    output_path = _create_output_path()

    main.assemble(["--header-segment", "-i", include_path, "test.eh", output_path])

    content = open(output_path, "rb").read()
    assert content[0:4] == b"\x7fELF"

    # if we are on Linux, we try to actually run our program.
    _assert_execution_output(output_path, b"aaaaa")

    os.remove(output_path)


def test_assemble_no_header(include_path):
    output_path = _create_output_path()

    main.assemble(["--no-header", "-i", include_path, "noheader.eh", output_path])

    content = open(output_path, "rb").read()
    assert content == b"\x00\x01\x02\x03"

    os.remove(output_path)
