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
from . import program

# always the case for ELF files
FILE_HEADER_SIZE = 52
PROGRAM_HEADER_ENTRY_SIZE = 32


class ElfHeader:
    '''The file header of an ELF file.'''

    def __init__(self, entry_label):
        self.entry_label = entry_label

    def get_size(self):
        return FILE_HEADER_SIZE

    def render(self, program):
        e_ident = b'\x7fELF' + struct.pack(
            '=BBBBB',
            1,  # ei_class
            2 if program.get_metadata().endianness == '>' else 1,  # ei_data
            1,  # ei_version
            0,  # ei_osabi
            0,  # ei_abiversion
        ) + b'\x00' * 7
        return e_ident + struct.pack(
            f'{program.get_metadata().endianness}HHIIIIIHHHHHH',
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
            0)  # e_shstrndx


class ProgramHeader:
    '''A program header entry in an ELF file.'''

    def get_size(self, program):
        return PROGRAM_HEADER_ENTRY_SIZE * len(program.get_segments())

    def render(self, program):
        return b''.join(
            struct.pack(
                f'{program.get_metadata().endianness}IIIIIIII',
                1,  # p_type = PT_LOAD
                segment.location_in_file,  # p_offset
                segment.location_in_memory,  # p_vaddr
                segment.location_in_memory,  # p_paddr
                segment.get_file_size(),  # p_filesz
                segment.get_size(),  # p_memsz
                segment.get_flags(),  # p_flags
                segment.get_align(program.get_metadata().align))  # p_align
            for segment in program.get_segments().values())


def get_header(entry_label):
    '''Returns the ELF header for the given entry_label and number of segments.'''
    return [ElfHeader(entry_label), ProgramHeader()]
