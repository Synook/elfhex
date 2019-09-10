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

"""This module contains the Preprocessor class, which preprocesses ELF input files,
resolving includes and fragment references.
"""

import copy
import lark
from . import util


class Preprocessor:
    """Preprocesses ELFHex files, parsing them and resolving includes and fragment
    references.
    """

    def __init__(self, file_loader):
        """
        Create a new preprocessor with the given file loader. The file loader must be a
        dictionary-like object which maps filenames to file contents. The values may
        also be two-tuples: in this case, the first element must contain the file
        contents, with the second containing the absolute or canonical path of the file.
        A standard file loader which searches the local file system is
        elfhex.FileLoader.
        """
        self.parser = util.get_parser()
        self.file_loader = file_loader

    def preprocess(self, path, max_fragment_depth=16):
        """Returns a syntax tree obtained by parsing the file located at the given path.
        This function also resolves the includes and fragment references in the file,
        ensuring that only the program declaration and segments are output in the final
        syntax tree. The return value of this function can then be used by
        elfhex.Transformer.

        The max_fragment_depth controls how many times fragment references will be
        resolved, as fragments can themselves contain fragment references. If 0, then
        no fragments can be resolved. An error will be raised if the set depth is
        exceeded.
        """
        if max_fragment_depth < 0:
            raise ValueError("max_fragment_depth must be greater than 0.")
        parsed = self._process_includes(path, set())
        fragments = self._gather_fragments(parsed)
        canonical = self._merge(parsed)
        for _ in range(0, max_fragment_depth):
            if not self._replace_fragments(canonical, fragments):
                break
        if self._replace_fragments(canonical, fragments):
            raise util.ElfhexError("Max recursion depth for fragments reached.")
        return canonical

    def _process_includes(self, path, seen, fragments_only=False):
        data = self.file_loader[path]
        if isinstance(data, tuple):
            data, path = data
        if path in seen:
            return []
        seen.add(path)

        parsed = self.parser.parse(data)
        results = [(parsed, fragments_only)]
        for node in parsed.find_data("include"):
            include = str(node.children[-1].children[0])[1:-1]
            child_fragments_only = len(node.children) > 1
            results.extend(
                self._process_includes(
                    include, seen, fragments_only or child_fragments_only
                )
            )
        return results

    @staticmethod
    def _gather_fragments(parsed):
        fragments = {}
        for program, _ in parsed:
            for fragment in program.find_data("fragment"):
                name, args, *contents = fragment.children
                fragments[str(name)] = {
                    "args": [str(name) for name in args.children],
                    "contents": contents,
                }
        return fragments

    @staticmethod
    def _merge_metadata(metadata, program):
        if metadata is None:
            metadata, = program.find_data("metadata")
        else:
            new_metadata, = program.find_data("metadata")
            if metadata.children[0:2] != new_metadata.children[0:2]:
                raise util.ElfhexError("Incompatible metadata.")
            metadata.children[2] = lark.Token(
                "INT",
                str(max(int(metadata.children[2]), int(new_metadata.children[2]))),
            )
        return metadata

    def _merge(self, parsed):
        canonical, _ = parsed[0]
        # Reset children (we don't want fragments in the output).
        merged = lark.Tree(canonical.data, [])
        segments = {}
        metadata = None
        for program, fragments_only in parsed:
            metadata = self._merge_metadata(metadata, program)
            if fragments_only:
                continue
            for segment in program.find_data("segment"):
                name, _, contents, auto_labels = segment.children
                if name in segments:
                    next(segments[name].find_data("segment_content")).children.extend(
                        contents.children
                    )
                    next(segments[name].find_data("auto_labels")).children.extend(
                        auto_labels.children
                    )
                else:
                    merged.children.append(segment)
                    segments[name] = segment
        merged.children.insert(0, metadata)
        return merged

    def _process_fragment_contents(self, contents, alias, args, ref_num):
        buffer = []
        for element in contents:
            if element.data == "fragment_var":
                buffer.extend(args[str(*element.children)])
                continue
            # allows for the use of vars in fragment args
            if element.data == "fragment_ref":
                for arg in element.children[2].children:
                    arg.children = self._process_fragment_contents(
                        arg.children, alias, args, ref_num
                    )
            if element.data in ("label", "abs", "rel"):
                label_name = str(element.children[0])
                if alias:
                    element = copy.deepcopy(element)
                    element.children[0] = lark.Token("NAME", f"{alias}.{label_name}")
                label_name = str(element.children[0])
                if label_name[0:2] == "__":
                    element = copy.deepcopy(element)
                    element.children[0] = lark.Token("NAME", f"__{ref_num}{label_name}")
            buffer.append(element)
        return buffer

    def _process_fragment_ref(self, fragment_info, fragments, ref_num, seen):
        start, name, params, alias = util.defaults(fragment_info, 4, None)
        if "!" in start.children:
            if name in seen:
                return []
            seen.add(name)
        if name not in fragments:
            raise util.ElfhexError(f"Non-existent fragment {name} referenced.")
        fragment = fragments[name]
        if len(fragment["args"]) != len(params.children):
            raise util.ElfhexError(
                f'Wrong number of arguments in reference to fragment "{name}".'
            )
        args = dict(
            zip(fragment["args"], map(lambda arg: arg.children, params.children))
        )
        return self._process_fragment_contents(
            fragment["contents"], alias, args, ref_num
        )

    def _replace_fragments(self, parsed, fragments):
        seen = set()
        ref_num = 0
        for segment in parsed.find_data("segment"):
            new_children = []
            for child in segment.children[2].children:
                if child.data == "fragment_ref":
                    new_children.extend(
                        self._process_fragment_ref(
                            child.children, fragments, ref_num, seen
                        )
                    )
                    ref_num += 1
                else:
                    new_children.append(child)
            segment.children[2].children = new_children
        return ref_num > 0
