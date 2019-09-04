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
from lark import Lark, Visitor, Token, Tree
from .util import ElfhexError, defaults


class Preprocessor:
    def __init__(self, file_provider):
        grammar_path = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), 'elfhex.lark')
        self.parser = Lark(open(grammar_path).read(),
                           parser='lalr', start='program')
        self.file_provider = file_provider

    def preprocess(self, input_path, max_fragment_depth):
        if max_fragment_depth < 0:
            raise ValueError("max_fragment_depth must be greater than 0.")
        parsed = self._process_includes(input_path, set())
        fragments = self._gather_fragments(parsed)
        canonical = self._merge(parsed)
        for _ in range(0, max_fragment_depth):
            if not self._replace_fragments(canonical, fragments):
                break
        if self._replace_fragments(canonical, fragments):
            raise ElfhexError("Max recursion depth for fragments reached.")
        return canonical

    def _process_includes(self, path, seen, fragments_only=False):
        data, full_path = self.file_provider[path]
        if full_path in seen:
            return []
        seen.add(full_path)

        parsed = self.parser.parse(data)
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
        # Reset children (we only want segments in the output).
        merged = Tree(canonical.data, [])
        segments = {}
        for program, fragments_only in parsed:
            if fragments_only:
                continue
            for segment in program.find_data('segment'):
                name, _, contents, auto_labels = segment.children
                if name in segments:
                    next(segments[name].find_data(
                        'segment_content')).children.extend(contents.children)
                    next(segments[name].find_data(
                        'auto_labels')).children.extend(auto_labels.children)
                else:
                    merged.children.append(segment)
                    segments[name] = segment
        return merged

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
            for child in segment.children[2].children:
                if child.data == 'fragment_ref':
                    new_children.extend(self._process_fragment_ref(
                        child.children, fragments, ref_num, seen))
                    ref_num += 1
                else:
                    new_children.append(child)
            segment.children[2].children = new_children
        return ref_num > 0
