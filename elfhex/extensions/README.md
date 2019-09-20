# Extensions

Extensions enhance the functionality of the ELFHex system. They are Python packages that are then referenced from ELFHex programs using the extension reference syntax:

```
:extension_name { content } # relative
::extension_name { content } # absolute
```

In the relative case, the system will search for the module `elfhex.extensions.extension_name`, while in the absolute case, it would just search for a module named `extension_name`. Periods are allowed in the extension name, to reference sub-modules. For example, `:x86.args` would refer to `elfhex.extensions.x86.args`.

In any case, extension modules should export a function named `parse(text)`. This function will be called with the `content` that the extension is invoked with, as a string. Note that if the extension language involves braces (`{}`), they must be balanced and not involve escaping, and may have whitespace placed around them before being passed to the extension. Otherwise, content will be transferred literally.

The `parse` function should return an object that implements two methods: `render` and `get_size`. These can optionally take two arguments, `program` and `segment`, that will contain the program and segment the extension is being invoked in.

The `get_size` method should return an `int` indicating how many bytes the output of the extension invocation will take up. The `render` method should return the actual bytes the extension invocation would place in the output. The main difference between these functions is that when `render` is invoked, label location information will be available from `Program.get_label_location()` and `Segment.get_labels()`. These will not be available when `get_size()` is called, as the assembler needs the size of all components in order to calculate label locations in the first place.

For an example extension, see [x86/args.py](x86/args.py).
