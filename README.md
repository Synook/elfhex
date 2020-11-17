# ELFHex

 [![Build Status](https://travis-ci.org/Synook/elfhex.svg?branch=master)](https://travis-ci.org/Synook/elfhex) [![Coverage Status](https://coveralls.io/repos/github/Synook/elfhex/badge.svg?branch=master)](https://coveralls.io/github/Synook/elfhex?branch=master) [![PyPI version](https://badge.fury.io/py/elfhex.svg)](https://pypi.org/project/elfhex/)

This is not an officially supported Google product.

ELFHex is a simple "assembler" designed for learning machine code. It takes programs comprising machine instructions and packages them into simple 32-bit ELF executable binaries. It aims to do the minimum amount of transformation necessary to keep the output binaries understandable and easy to relate back to the source files. Nevertheless, it has several language features (beyond just constructing the ELF header) to make it more convenient than just trying to write an executable using a hex editor.

## Usage

ELFHex requires at least Python 3.6. To install the package, run:

```shell
pip install elfhex
```

This installs a command-line tool named `elfhex`. View its usage with `elfhex -h`. In general, the tool needs an input source file and a location for the output executable. Other options include the ability to omit the ELF header in the output, and set the starting memory address and entry point label.

### Development

This project uses Python 3.6 and `pipenv`. In order to install dependencies, run `pipenv install --dev`. The program can then be run using `python -m elfhex`. To execute the tests, run `pytest`.

There are some pre-commit hooks that check for certain formatting and other issues, which can be installed using `pre-commit install`. Run [`black .`](https://black.readthedocs.io/en/stable/) to auto-format changes, and `flake8` to check for PEP 8 violations.

To build a package, first generate `requirements.txt`, and then use `setuptools` to build the distributable artifacts.

```shell
pipenv run pipenv_to_requirements
pipenv run python setup.py sdist bdist_wheel
```

### As a module

The ELFHex module can also be imported. The command-line tool's usage of it can be seen in `__main__.py`. In general, there are separate components that deal with preprocessing, transformation, rendering, and the ELF header.

```python
import elfhex
file_loader = elfhex.FileLoader(include_paths)
preprocessor = elfhex.Preprocessor(file_loader)
preprocessed = preprocessor.preprocess(input_path, max_fragment_depth)
program = elfhex.Transformer().transform(preprocessed)
header = elfhex.elf.get_header(entry_label)
program.prepend_header_to_first_segment(header)
output = program.render(memory_start)
```

## Language reference

Source files are written in `.eh` format. Each EH file comprises the *program declaration*, *includes* of other source files,  *segments*, corresponding to segments in the output ELF file, and *fragments*, which can be copied into segment code. Each segment has a name, various arguments, and contents.

```
program 3 < 4096 # program declaration

include "file.eh" # segments will be merged by name
include fragments "some/file.eh" # only fragments will be included

segment segment_name(flags: rx) {
  1e e7 =10d4 "string" # bytes, numbers, and strings
  [label] <label:4> <<label + 4>> # labels and references
  @fragment_name(aa, <label>) # fragment references
  [[auto_label: 4 auto_label2: 1024]] # auto labels
}

fragment fragment_name(arg1, arg2) {
  $arg1 # fragment parameter references
  ab cd # otherwise, the same content as segments except for auto labels
}
```

Sections (e.g., `.text`, `.bss`, etc.) are not represented, as they are not necessary in an executable ELF file. After all includes are processed, there must be at least one segment which defines a label named `_start` (configurable). This label will be used as the entry point for program execution.

## Program declaration

Every source file must begin with the program declaration. This defines the target machine (the numeric value for `e_machine` in the ELF header), the endianness of the file, either `<` (little) or `>` (big), and the default segment alignment. For example, `program 3 < 4096` would indicate an `e_machine` value of 3 (x86), little-endian output, and a default alignment of 4096 bytes.

All included source files must have the same `e_machine` value and endianness, otherwise an error is emitted. If the alignments differ, then the largest value overall is used.

## Segments

All segments have names in the source code. This name is not transferred to the packaged binary, but serves as a reference when processing includes and references. Segments can also define metadata, including flags, size, and alignment. The `flags` (r, rw, rx, or rwx), `size` in bytes, and `alignment` are used to construct the program header entry for the segment. The maximum of the size argument and length of the actual contents is used to determine the memory size provided in the program header entry. The default segment alignment is 0x1000 bytes, which is the x86 page size. Generally this doesn't need to be changed, and going below this can lead to issues.

## Fragments

Fragments are similar to segments, but do not define metadata. They are also similar in contents to segments, however, by themselves they do not appear in the output. Instead, fragments can be referenced from segments and other fragments using `@fragment_name(args)`. This will insert the contents of the fragment directly at the location of the reference. Fragments can themselves contain references to other fragments. In this case, the references are iteratively resolved until a configurable limit. If that limit is reached, an error is emitted.

### Fragment parameters

Fragments can also define parameters. These parameters can then be referenced in the fragment body using `$parameter_name`. This will literally insert the contents provided for the parameter when the fragment is referenced, at that point. When referencing a fragment, the values for each parameter are supplied in a comma-delimited list in parentheses after the fargment name.

Any byte sequence can be used for the value of the argument, including labels, references, other fragment references, and even parameter values. For example, the following is valid:

```
fragment f1(a, b) {
  @f2($b ff $a @f2($a dd))
}

fragment f2(a) {
  $a ee
}
```

In this case, `@f1(00, 11)` would result in `11 ff 00 ee 00 dd ee ee`.

### Name collision prevention

Since the same fragment can be referenced multiple times, labels in fragments may end up being defined multiple times. To avoid this, fragments can define "local" labels and references, which are prefixed with `__` (e.g.`[__only_use_in_fragment]`). These are clobbered at compile-time so that they are different for every reference to the fragment. This allows the same fragment to be referenced multiple times. If a fragment contains a bare label but needs to be referenced more than once, the user of the fragment can also prevent name collisions by using fragment alias syntax, e.g. `@fragment_name(args)(alias)`. This will prefix all labels in that instance of the fragment with `alias.`, once again ensuring they do not collide, but also allowing them to be referenced from outside the fragment.

In certain situations, it may be desirable to only include a fragment once in the program. In these cases, starting the fragment reference with `@!` (e.g., `@!fragment_name()`) will ensure that the fragment in question will only be included once across all references to it (that also start with `@!`). This will not affect references not prefixed by `@!`.

## Segment and fragment contents

Generally speaking, the contents of a segment or fragment is a sequence of bytes. These bytes can be represented either literally, or as a reference.

### Literals

The most fundamental is using literal hexadecimal bytes, e.g. `a1 b8`.

For convenience, bytes can also be represented using padded literals in binary, decimal, or hexadecimal, e.g. `=10d4` (`0a 00 00 00`), `+2ah2` (`2a 00`) or `-01011011b` (`a5`). In these cases, the first character represents the sign (if `=` is used, unsigned conversion will occur), the digits after that represent the number itself, the character at the end indicates the base (`b` for binary, `d` for decimal, and `h` for hexadecimal), and the number after the base character represents the number of bytes that the literal will be padded to (one byte by default).

String literals are also supported, e.g. `"Hello"` (`48 65 6c 6c 6f`). These will not be null terminated, but directly converted to each character's ASCII value. Only printable characters are representable; for other characters the hex byte should be written directly (e.g., `"test" 0a 00`).

### Labels and references

In order to support pointers to other locations in the code, labels and references are supported. Labels are defined using square brackets, e.g. `[a_label]`. Absolute and relative references can then be made to that label using `<<a_label>>` and `<a_label>` respectively. Absolute references across segments can also be made, and a constant offset can be provided, e.g. `<<segment: a_label + 4>>`. Relative references can also specify their width in bytes, e.g. `<a_label:4>` (the default width is one byte).

In both cases, the reference is replaced with the appropriate byte sequence at compile time.

### Fragment references

As [described above](#fragments), the contents of fragments can be inserted into the source by referencing them with the `@` symbol, for example, a fragment with name `fragment_name` would be referenced with `@fragment_name()`.

### Auto labels

At the end of segments (but not fragments), a list of "auto labels" can be defined. All labels in the list are placed between a single pair of double square brackets, for example, `[[label1: 4 label2: 8]]`.

Each auto label comprises a name, along with a width. These labels do not point to contents in the file image, and refer to a memory location in the segment after the file contents. The width defines the number of bytes between the location of the label and the next artifact (other auto label) in the memory layout. The memory size of the segment will be adjusted accordingly to accommodate all the defined auto labels.

For example, consider a segment defined as:

```
segment test() { ab cd [[label: 4 label2: 8]] }
```

The file size of this segment would be 2, but the memory size would be 14 (2 + 4 + 8). If the beginning offset of the segment was byte 1000, then `label` would refer to offset 1002, and `label2` to offset 1006. These labels can then be refered to as usual.

Auto labels can only appear at the end of a segment, so that they are not assigned over segment content. When segments are merged during the file inclusion process, the auto label lists are also concatenated to each other.

### Extensions

Since the ELFHex language itself is quite basic, extensions can be used to enhance the functionality of the system. Extensions are invoked using:

```
:extension_name { extension_content }
```

At this point, the `extension_content` is entirely up to the extension named `extension_name` to parse and convert into bytes, which are then placed in the final output.

Extensions are defined using Python modules. If a single colon (`:`) is used at the start, then `elfhex.extensions.extension_name` is imported, while if a double colon (`::`) is used then `extension_name` is imported instead. For example, the following code would invoke the [`x86.args`](elfhex/extensions/x86/args.py) extension:

```
:x86.args { ecx, [ebx + esi * 8 - 4] }
```

For more information on extension structure, see the [extension development documentation](elfhex/extensions/README.md).

### Comments

Comments can be included in the code, prefixed by `#`. Any characters after this and before the end of the line will be ignored.

## Includes

Various source files can be composed into a single executable using the include statement: `include "filename.eh"`. This works very simply: for each segment in the included file, if the segment name matches one in the file that included it, the contents is simply appended to the bottom of that segment. Otherwise, a new segment is created. All fragments in the included file are also made available. No name changes are made during the inclusion process, so collisions are possible. Care should be taken with naming to mitigate this.

If only fragments need to be imported from a file, `include fragments "..."` can be used instead. With this statement, no segments from the file, or its includes, will be incorporated into the output.

Recursive inclusion is possible (that is, the includes for each included file are also processed). If a file has already been included, all future include statements for it are ignored.

As stated earlier, all included files must have the same target machine and endianness in the program declaration. Alignments can differ but the largest value will be used.

## Example

This program simply prints out "hello, world" five times.

```
program 3 < 4096

include fragments "other.eh"

segment text(flags: rx) {
  [_start]

  # print hello to stdout
  @syscall3(=4d4, =1d4, <<strings:hello>>, =13d4)

  # if ++counter <= 5 goto loop
  ff :x86.args{ 0, [dword ptr data:counter] }
  81 =00111101b <<data:counter>> =5d4
  72 <_start>

  @exit()
}

segment data(flags: rw) {
  [[counter: 4]]
}

segment strings(flags: r) {
  [hello] "Hello, world" 0a
}
```

other.eh:

```
program 3 < 4096

fragment exit() {
  @common_syscall(=1d4)
}

fragment syscall3(number, ebx, ecx, edx) {
  bb $ebx
  b9 $ecx
  ba $edx
  @common_syscall($number)
}

fragment syscall(number) {
  b8 $number
  cd 80
}
```

For more examples, see the samples directory.
