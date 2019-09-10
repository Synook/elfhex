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

"""This module contains the FileLoader class, which reads files from the filesystem."""

import os
from . import util


class FileLoader:
    """A dictionary-like object that will search the provided search_dirs for the
    provided filename, returning the (contents, absolute_path) if found.
    """

    def __init__(self, search_dirs):
        """Creates a new file loader that will search in the provided directories."""
        self.search_dirs = search_dirs

    def __getitem__(self, path):
        """
        Returns the contents of the file at the path, along with the absolute location
        of the file. Returns an ElfhexError if the file can't be found after searching
        all directories.
        """
        for directory in self.search_dirs:
            try:
                full_path = os.path.abspath(os.path.join(directory, path))
                contents = open(full_path).read()
                return contents, full_path
            except FileNotFoundError:
                pass
        raise util.ElfhexError(f"Couldn't find {path} in {self.search_dirs}.")
