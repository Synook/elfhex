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
"""An ELFHex extension that computes x86 argument or "ModR/M" bytes, represented in
Intel style. Since argument order is determined by the opcode, the register always
comes first, and can also be specified using a number, for ease when using unary
opcodes (which usually used the "register" field to help determine the instruction).
Labels can be used, with segments represented by a "segment_name:" prefix.

This module can also be used separately to help calcuate ModR/M bytes. For example:

    args = X86Args(
        Register.EBX,
        Memory(
            base=Register.ESI,
            index=Index(Register.EBP, Scale.TWO)
        )
    )
    print(args.render()) # b'\x1cn'
    args = parse("ebx, [esi + ebp * 2]")
    print(args.render()) # also b'\x1cn'
"""
import enum
import math
import os
import struct

import lark


class X86Args:
    """Represents the argument bytes of an x86 instruction."""

    def __init__(self, register, memory):
        """Creates a new x86 arguments object with the given register and memory
        components. The "memory" component can either be a Register itself or a Memory
        instance.
        """
        self.register = register
        self.memory = memory

    def render(self, program=None, segment=None):
        """Returns the byte representation of the arguments. If program and segment
        are supplied, then pointers will be resolved. If not, all pointers will have
        value 0.
        """
        if isinstance(self.memory, Register):
            return bytes(
                [(0b11 << 6) | self.memory.get_value() | (self.register.get_bitmask())]
            )
        return bytes(self.memory.render(self.register, program, segment))

    def get_size(self):
        """Return the number of bytes these arguments will take up."""
        return len(self.render())


class Memory:
    """Represents the memory component of the x86 argument bytes."""

    def __init__(self, base=None, index=None, disp=0):
        """Creates a new memory instance with the provided base, index, and
        displacement. All components are optional.
        """
        self.base = base
        self.index = index
        self.disp = disp

    def render(self, register, program, segment):
        """Produce the byte representation of this memory instance, given a register.
        Only supposed to be called internally by X86Args.render().
        """
        first_byte = register.get_bitmask()
        if not self.base and not self.index:
            # disp32 only
            return self._extend_disp(
                [first_byte | 0b00000101], program, segment, set_mod=False
            )
        if self.index is None:
            first_byte |= self.base.get_value()
            if self.base == Register.ESP:
                # special no-index SIB for esp
                return self._extend_disp([first_byte, 0x24], program, segment)
            # no need for SIB (if base is esp must use SIB)
            if not self.disp and self.base == Register.EBP:
                # ebp but no disp, so use mod=1 and disp=0
                return [first_byte | 0b1 << 6, 0]
            # set disp bytes
            return self._extend_disp([first_byte], program, segment)
        # must use SIB
        first_byte |= 0b100
        second_byte = self.index.get_bitmask()
        if self.base is None:
            # special index + disp case (mod remains 0)
            second_byte |= 0b101
            return self._extend_disp(
                [first_byte, second_byte], program, segment, set_mod=False, fix32=True
            )
        second_byte |= self.base.get_value()
        return self._extend_disp([first_byte, second_byte], program, segment)

    def _extend_disp(self, output, program, segment, set_mod=True, fix32=False):
        first_byte = output[0]
        if isinstance(self.disp, int):
            if self.disp != 0 or fix32:
                success = False
                if not fix32:
                    try:
                        disp = struct.pack("<b", self.disp)
                        first_byte |= 1 << 6
                        success = True
                    except struct.error:
                        pass
                if not success:
                    disp = struct.pack("<i", self.disp)
                    first_byte |= 0b10 << 6
            else:
                disp = []
        else:
            disp = struct.pack("<I", self.disp.get_value(program, segment) or 0)
            first_byte |= 0b10 << 6
        if set_mod:
            output[0] = first_byte
        output.extend(bytearray(disp))
        return output


class Pointer:
    """Represents a pointer to a location in the program."""

    def __init__(self, label, segment=None):
        """Creates a new pointer to the given label. If segment is None or not
        provided then the current segment will be used.
        """
        self.label = label
        self.segment = segment

    def get_value(self, program, segment):
        if program is None or segment is None:
            return 0
        segment_name = self.segment or segment.get_name()
        return program.get_label_location(self.label, segment_name)


class Register(enum.Enum):
    """Represents an x86 register."""

    EAX = 0
    ECX = 1
    EDX = 2
    EBX = 3
    ESP = 4
    EBP = 5
    ESI = 6
    EDI = 7

    @classmethod
    def from_name(cls, name):
        """Returns the appropriate register for the given name, which can either be
        the register's name (for any width), or a number.
        """
        try:
            return cls(int(name))
        except ValueError:
            pass
        name = name.upper()
        if name in cls.aliases:
            return cls.aliases[name]
        return cls[name]

    def get_value(self):
        return self.value

    def get_bitmask(self):
        return self.get_value() << 3


Register.aliases = {
    "AL": Register.EAX,
    "CL": Register.ECX,
    "DL": Register.EDX,
    "BL": Register.EBX,
    "AH": Register.ESP,
    "CH": Register.EBP,
    "DH": Register.ESI,
    "BH": Register.EDI,
}


class Scale(enum.Enum):
    """Represents the scale of a scaled index in the SIB byte."""

    ONE = 1
    TWO = 2
    FOUR = 4
    EIGHT = 8

    def get_bitmask(self):
        return int(math.log(self.value, 2)) << 6


class Index:
    """Represents the scaled index of the SIB byte."""

    def __init__(self, register, scale=Scale.ONE):
        """Create a new scaled index with the given register and scale."""

        if register == Register.ESP:
            raise ValueError("The ESP register can't be used as the index.")
        self.register = register
        self.scale = scale

    def get_bitmask(self):
        return self.scale.get_bitmask() | self.register.get_bitmask()


class _Transformer(lark.Transformer):
    def args(self, items):
        register, memory = items
        return X86Args(register, memory)

    def reg_mem(self, items):
        value, = items
        return value

    def pointer(self, items):
        if len(items) == 2:
            segment, label = items
            return Pointer(label, segment)
        label, = items
        return Pointer(label)

    def literal(self, items):
        value, = items
        if value.type == "HEX":
            number = int(value[:-1], 16)
        else:
            number = int(value)
        return number

    def register(self, items):
        value, = items
        return Register.from_name(value)

    def memory(self, items):
        """The parsing for this part unfortunately has to be flat, as the language is
        very flexible.
        """
        base = None
        index = None
        disp = 0
        if len(items) == 1:
            if isinstance(items[0], Register):
                base = items[0]
            else:
                disp = items[0]
        elif len(items) == 2:
            p1, p2 = items
            if isinstance(p2, Scale):
                # must be [index * scale]
                index = Index(p1, p2)
            else:
                base = p1
                if isinstance(p2, Register):
                    # must be [base + index]
                    index = Index(p2, Scale(1))
                else:
                    # must be [base + disp]
                    disp = p2
        elif len(items) == 3:
            p1, p2, p3 = items
            if isinstance(p3, Scale):
                # must be [base + index * scale]
                base = p1
                index = Index(p2, p3)
            elif isinstance(p2, Scale):
                # must be [index * scale + disp]
                index = Index(p1, p2)
                disp = p3
            else:
                # must be [base + index + disp]
                base = p1
                index = Index(p2, Scale(1))
                disp = p3
        else:
            # all components present
            base, index, scale, disp = items
            index = Index(index, scale)
        return Memory(base, index, disp)

    def disp(self, items):
        sign, value = items
        if sign == "-":
            value *= -1
        return value

    def disp_only(self, items):
        item, = items
        return item

    def scale(self, items):
        value, = items
        return Scale(int(value))


_parser = lark.Lark(
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "x86.lark")).read(),
    parser="lalr",
    start="args",
)
_transformer = _Transformer()


def parse(text):
    """Returns the given text representing x86 arguments in Intel syntax (register
    first) as an X86Args instance.
    """
    return _transformer.transform(_parser.parse(text))
