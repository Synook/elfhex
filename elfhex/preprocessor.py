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
import copy
from lark import Visitor, Token
from .util import ElfhexError, defaults


class Preprocessor:
    def __init__(self, parser, args):
        self.parser = parser
        self.args = args
        self.search_dirs = [
            os.path.abspath(directory)
            for directory in self.args.include_path
        ]

    def preprocess(self):
        parsed = self._process_includes(self.args.input_path)
        fragments = self._gather_fragments(parsed)
        canonical = self._merge(parsed)
        for i in range(0, self.args.max_fragment_depth):
            if not self._replace_fragments(canonical, fragments):
                break
            if i == self.args.max_fragment_depth - 1:
                raise ElfhexError("Max recursion depth for fragments reached.")
        return canonical

    def _try_open(self, path):
        f = None
        for directory in self.search_dirs:
            try:
                full_path = os.path.abspath(os.path.join(directory, path))
                f = open(full_path)
                break
            except FileNotFoundError:
                pass
        if not f:
            raise ElfhexError("Couldn't find {path} in {self.search_dirs}.")
        return f, full_path

    def _process_includes(self, path, seen=set(), fragments_only=False):
        f, full_path = self._try_open(path)
        if full_path in seen:
            return []
        seen.add(full_path)

        parsed = self.parser.parse(f.read())
        results = [(parsed, fragments_only)]
        for node in parsed.find_data('include'):
            include = str(node.children[-1].children[0])[1:-1]
            child_fragments_only = len(node.children) > 1
            results.extend(self._process_includes(
                include, seen, fragments_only or child_fragments_only))
        return results

    def _gather_fragments(self, parsed):
        fragments = {}
        for program, _ in parsed:
            for fragment in program.find_data('fragment'):
                name, args, *contents = fragment.children
                fragments[str(name)] = {
                    'args': [str(name) for name in args.children],
                    'contents': contents}
        return fragments

    def _merge(self, parsed):
        canonical, _ = parsed[0]
        segments = {}
        for segment in canonical.children:
            if segment.data == 'segment':
                segments[str(segment.children[0])] = segment
        for program, fragments_only in parsed[1:]:
            if fragments_only:
                continue
            for segment in program.find_data('segment'):
                name, _, contents = segment.children
                if name in segments:
                    segments[name].children.extend(contents)
                else:
                    canonical.children.append(segment)
                    segments[name] = segment
        return canonical

    def _process_fragment_contents(self, contents, alias, args, ref_num):
        buffer = []
        for element in contents:
            if element.data == 'fragment_var':
                buffer.extend(args[str(*element.children)])
                continue
            # allows for the use of vars in fragment args
            if element.data == 'fragment_ref':
                for arg in element.children[2].children:
                    arg.children = self._process_fragment_contents(
                        arg.children, alias, args, ref_num)
            if element.data in ('label', 'abs', 'rel'):
                label_name = str(element.children[0])
                if alias:
                    element = copy.deepcopy(element)
                    element.children[0] = Token(
                        "NAME", f"{alias}.{label_name}")
                label_name = str(element.children[0])
                if label_name[0:2] == '__':
                    element = copy.deepcopy(element)
                    element.children[0] = Token(
                        "NAME", f"__{ref_num}{label_name}")
            buffer.append(element)
        return buffer

    def _process_fragment_ref(self, fragment_info, fragments, ref_num, seen):
        start, name, params, alias = defaults(fragment_info, 4, None)
        if '!' in start.children:
            if name in seen:
                return []
            else:
                seen.add(name)
        if not name in fragments:
            raise ElfhexError(f'Non-existent fragment {name} referenced.')
        fragment = fragments[name]
        if len(fragment['args']) != len(params.children):
            raise ElfhexError(
                f'Wrong number of arguments in reference to fragment "{name}".')
        args = dict(zip(
            fragment['args'],
            map(lambda arg: arg.children, params.children)))
        return self._process_fragment_contents(fragment['contents'], alias, args, ref_num)

    def _replace_fragments(self, parsed, fragments):
        seen = set()
        ref_num = 0
        for segment in parsed.find_data('segment'):
            new_children = []
            for child in segment.children[2:]:
                if child.data == 'fragment_ref':
                    new_children.extend(self._process_fragment_ref(
                        child.children, fragments, ref_num, seen))
                    ref_num += 1
                else:
                    new_children.append(child)
            segment.children[2:] = new_children
        return ref_num > 0
