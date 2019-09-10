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

"""Assemble an ELFHex source file into an ELF executable binary."""

import sys
import argparse
from lark.exceptions import LarkError, VisitError
import elfhex


def _parse_args(argv=None):
    argparser = argparse.ArgumentParser(
        prog="elfhex",
        description='A ELF hexadecimal "assember" (elfhex).',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    argparser.add_argument(
        "input_path", type=str, help="Location of the input EH file."
    )
    argparser.add_argument(
        "output_path", type=str, help="Location for the output executable."
    )
    argparser.add_argument(
        "-s",
        "--memory-start",
        type=lambda n: int(n, 16),
        default="08048000",
        help="The starting memory address in hexadecimal.",
    )
    argparser.add_argument(
        "-f",
        "--max-fragment-depth",
        type=int,
        default=16,
        help="The maximum depth when resolving fragment references.",
    )
    argparser.add_argument(
        "-e",
        "--entry-label",
        type=str,
        default="_start",
        help="The label to use as the entry point.",
    )
    argparser.add_argument(
        "-i",
        "--include-path",
        action="append",
        default=["."],
        help="A path to search for source files (repeatable).",
    )
    argparser.add_argument(
        "-r", "--no-header", action="store_true", help="Do not output the ELF header."
    )
    argparser.add_argument(
        "-H",
        "--header-segment",
        action="store_true",
        help="Place the ELF header in its own segment.",
    )

    return argparser.parse_args(argv) if argv else argparser.parse_args()


def assemble(argv=None):
    """Assembles an ELFHex source program into an executable, with the provided
    arguments taken from the command line by default.
    """

    # Parse arguments.
    args = _parse_args(argv)

    # Preprocess source (resolves includes and fragment references).
    preprocessed = elfhex.Preprocessor(elfhex.FileLoader(args.include_path)).preprocess(
        args.input_path, args.max_fragment_depth
    )

    # Transform the syntax into a Program instance.
    program = elfhex.Transformer().transform(preprocessed)

    if not args.no_header:
        # Add the ELF header.
        header = elfhex.elf.get_header(args.entry_label)
        if args.header_segment:
            program.prepend_header_segment(header)
        else:
            program.prepend_header_to_first_segment(header)

    # Generate the binary output.
    output = program.render(args.memory_start)

    # Output the resulting blob.
    open(args.output_path, "wb").write(output)
    print(f"Assembled. Total size: {len(output)} bytes.")


def _report_error(ex):  # pragma: no cover
    print(ex, file=sys.stdout)
    print("Errors were encountered while processing input.", file=sys.stdout)
    exit(1)


def main():  # pragma: no cover
    """Reads arguments from the command line and assembles an ELFHex source file into
    an executable binary.
    """
    try:
        assemble()
    except VisitError as ex:
        _report_error(ex.orig_exc)
    except (LarkError, elfhex.ElfhexError) as ex:
        _report_error(ex)


if __name__ == "__main__":  # pragma: no cover
    main()
