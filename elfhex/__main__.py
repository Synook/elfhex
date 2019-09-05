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

import sys
import os
import argparse
from lark import Lark
from lark.exceptions import LarkError, VisitError
import elfhex


def parse_args():
    argparser = argparse.ArgumentParser(
        prog='elfhex', description='A ELF hexadecimal "assember" (elfhex).',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    argparser.add_argument(
        'input_path', type=str,
        help='Location of the input EH file.')
    argparser.add_argument(
        'output_path', type=str,
        help='Location for the output executable.')
    argparser.add_argument(
        '-s', '--memory_start', type=lambda n: int(n, 16), default='08048000',
        help='The starting memory address in hexadecimal.')
    argparser.add_argument(
        '-f', '--max_fragment_depth', type=int, default=16,
        help='The maximum depth when resolving fragment references.')
    argparser.add_argument(
        '-e', '--entry-label', type=str, default='_start',
        help='The label to use as the entry point.')
    argparser.add_argument(
        '-i', '--include_path', action='append', default=['.'],
        help='A path to search for source files (repeatable).')
    argparser.add_argument(
        '-r', '--no_header', action='store_true',
        help='Do not output the ELF header.')

    return argparser.parse_args()


def report_error(e):
    print(e, file=sys.stdout)
    print('Errors were encountered while processing input.', file=sys.stdout)


def main():
    # parse arguments
    args = parse_args()

    try:
        # preprocess source (resolves includes and fragment references)
        preprocessed = \
            elfhex.Preprocessor(elfhex.FileLoader(args.include_path)) \
            .preprocess(args.input_path, args.max_fragment_depth)

        # transform the syntax into a Program instance
        program = elfhex.Transformer().transform(preprocessed)

        # "assemble" it into an ELF executable
        if args.no_header:
            program.set_label_locations(0, args.memory_start)
            return program.render()
        else:
            elf = elfhex.Elf()
            program.set_label_locations(
                elf.get_header_size(program), args.memory_start)
            output = elf.render(program, args.entry_label) + program.render()

        # output resulting blob
        open(args.output_path, 'wb').write(output)
        print(f"Assembled. Total size: {len(output)} bytes.")

    except VisitError as e:
        report_error(e.orig_exc)
    except (LarkError, elfhex.ElfhexError) as e:
        report_error(e)


if __name__ == '__main__':
    main()
