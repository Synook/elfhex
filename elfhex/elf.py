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

# always the case for ELF files
FILE_HEADER_SIZE = 52
PROGRAM_HEADER_ENTRY_SIZE = 32


class Elf:
    '''Generates ELF headers based on supplied ELFHex programs.'''

    def get_header_size(self, program):
        '''Returns the size the header would be for a given program.'''
        return FILE_HEADER_SIZE + PROGRAM_HEADER_ENTRY_SIZE * (len(program.get_segments()) + 1)

    def render(self, program, entry_label):
        '''
        Returns the binary representation of the ELF header for the given program and entry
        label.
        '''
        align = program.get_metadata().align
        endianness = program.get_metadata().endianness
        start = program.get_memory_start()
        header_size = self.get_header_size(program)

        e_ident = b'\x7fELF' + struct.pack(
            '=BBBBB',
            1,  # ei_class
            2 if endianness == '>' else 1,  # ei_data
            1,  # ei_version
            0,  # ei_osabi
            0,  # ei_abiversion
        ) + b'\x00' * 7
        file_header = e_ident + struct.pack(
            f'{endianness}HHIIIIIHHHHHH',
            0x2,  # e_type = ET_EXEC
            program.get_metadata().machine,  # e_machine
            1,  # e_version
            program.get_label_location(entry_label),  # e_entry
            FILE_HEADER_SIZE,  # e_phoff
            0,  # e_shoff
            0,  # e_flags
            FILE_HEADER_SIZE,  # e_ehsize
            PROGRAM_HEADER_ENTRY_SIZE,  # e_phentsize
            len(program.get_segments()) + \
            1,  # e_phnum
            0,  # e_shentsize
            0,  # e_shnum
            0,  # e_shstrndx
        )
        program_header_entries = []
        program_header_entries.append(struct.pack(
            f'{endianness}IIIIIIII',
            1,  # p_type = PT_LOAD
            0,  # p_offset
            start,  # p_vaddr
            start,  # p_paddr
            header_size,  # p_filesz
            header_size,  # p_memsz
            0x5,  # p_flags
            align,  # p_align
        ))
        for _, segment in program.get_segments():
            program_header_entries.append(struct.pack(
                f'{endianness}IIIIIIII',
                1,  # p_type = PT_LOAD
                segment.location_in_file,  # p_offset
                segment.location_in_memory,  # p_vaddr
                segment.location_in_memory,  # p_paddr
                segment.get_file_size(),  # p_filesz
                segment.get_size(),  # p_memsz
                segment.get_flags(),  # p_flags
                segment.get_align(align),  # p_align
            ))
        return file_header + b''.join(program_header_entries)
