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

"""This module creates ELF headers for use with ELFHex Program instances. The headers
generated here are program-independent; their exact form is determined during program
rendering.
"""

import struct

# always the case for ELF files
FILE_HEADER_SIZE = 52
PROGRAM_HEADER_ENTRY_SIZE = 32


class ElfHeader:
    """The file header of an ELF file."""

    def __init__(self, entry_label):
        """Creates a new ELF file header, where the entry address points to the first
        location of the given label in any program segment.
        """
        self.entry_label = entry_label

    @staticmethod
    def get_size():
        """Returns the size of the file header."""
        return FILE_HEADER_SIZE

    def render(self, program):
        """Returns the binary representation of the file header."""
        e_ident = (
            b"\x7fELF"
            + struct.pack(
                "=BBBBB",
                1,  # ei_class
                2 if program.get_metadata().endianness == ">" else 1,  # ei_data
                1,  # ei_version
                0,  # ei_osabi
                0,  # ei_abiversion
            )
            + b"\x00" * 7
        )
        return e_ident + struct.pack(
            f"{program.get_metadata().endianness}HHIIIIIHHHHHH",
            0x2,  # e_type = ET_EXEC
            program.get_metadata().machine,  # e_machine
            1,  # e_version
            program.get_label_location(self.entry_label),  # e_entry
            FILE_HEADER_SIZE,  # e_phoff
            0,  # e_shoff
            0,  # e_flags
            FILE_HEADER_SIZE,  # e_ehsize
            PROGRAM_HEADER_ENTRY_SIZE,  # e_phentsize
            len(program.get_segments()),  # e_phnum
            0,  # e_shentsize
            0,  # e_shnum
            0,  # e_shstrndx
        )


class ProgramHeaders:
    """The program headers array in an ELF file."""

    @staticmethod
    def get_size(program):
        """Returns the size of the program headers array based on the number of segments
        in the program.
        """
        return PROGRAM_HEADER_ENTRY_SIZE * len(program.get_segments())

    @staticmethod
    def render(program):
        """Returns the binary representation of the program headers array."""
        return b"".join(
            struct.pack(
                f"{program.get_metadata().endianness}IIIIIIII",
                1,  # p_type = PT_LOAD
                segment.location_in_file,  # p_offset
                segment.location_in_memory,  # p_vaddr
                segment.location_in_memory,  # p_paddr
                segment.get_file_size(),  # p_filesz
                segment.get_size(),  # p_memsz
                segment.get_flags(),  # p_flags
                segment.get_align(program.get_metadata().align),  # p_align
            )
            for segment in program.get_segments().values()
        )


def get_header(entry_label):
    """Returns an ELF header where the entry address will point to the given entry
    label.
    """
    return [ElfHeader(entry_label), ProgramHeaders()]
