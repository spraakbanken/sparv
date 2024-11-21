# Utilities

Sparv provides a variety of utility functions, classes, and constants that are useful across different modules. These
utilities are primarily imported from `sparv.api.util` and its submodules. For example:

```python
from sparv.api.util.system import call_binary
```

## Constants

The `sparv.api.util.constants` module includes several predefined constants that are used throughout the Sparv pipeline:

- `DELIM = "|"`: Delimiter character used to separate ambiguous results.
- `AFFIX = "|"`: Character used to enclose results, marking them as a set.
- `SCORESEP = ":"`: Character that separates an annotation from its score.
- `COMPSEP = "+"`: Character used to separate parts of a compound.
- `UNDEF = "__UNDEF__"`: Value representing undefined annotations.
- `OVERLAP_ATTR = "overlap"`: Name for automatically created overlap attributes.
- `SPARV_DEFAULT_NAMESPACE = "sparv"`: Default namespace used when annotation names collide and `sparv_namespace` is not
  set in the configuration.
- `UTF8 = "UTF-8"`: UTF-8 encoding.
- `LATIN1 = "ISO-8859-1"`: Latin-1 encoding.
- `HEADER_CONTENTS = "contents"`: Name of the annotation containing header contents.

## Export Utils

`sparv.api.util.export` provides utility functions for preparing data for export.

### gather_annotations()

Calculate the span hierarchy and the `annotation_dict` containing all annotation elements and attributes. Returns a
`spans_dict` and an `annotation_dict` if `flatten` is `True`, otherwise returns `span_positions` and `annotation_dict`.

**Parameters**:

- `annotations`: List of annotations to include.
- `export_names`: Dictionary mapping annotation names to export names.
- `header_annotations`: List of header annotations.
- `source_file`: Source filename.
- `flatten`: Set to `True` to return the spans as a flat list. Default: `True`
- `split_overlaps`: Set to `True` to split up overlapping spans. Default: `False`

### get_annotation_names()

Retrieve a list of annotations, token attributes, and a dictionary translating annotation names to export names.

**Parameters**:

- `annotations`: List of elements:attributes (annotations) to include.
- `source_annotations`: List of elements:attributes from the source file to include. If not specified, includes
  everything.
- `source_file`: Name of the source file.
- `source_files`: List of names of source files (alternative to `source_file`).
- `token_name`: Name of the token annotation.
- `remove_namespaces`: Set to `True` to remove all namespaces in `export_names` unless names are ambiguous. Default:
  `False`
- `keep_struct_names`: Set to `True` to include the annotation base name (everything before ":") in `export_names` for
  structural attributes. Default: `False`
- `sparv_namespace`: Namespace to add to all Sparv annotations.
- `source_namespace`: Namespace to add to all annotations present in the source.

### get_header_names()

Retrieve a list of header annotations and a dictionary for renamed annotations.

**Parameters**:

- `header_annotation_names`: List of header elements:attributes from the source file to include. If not specified,
  include everything.
- `source_file`: Name of the source file.
- `source_files`: List of names of source files (alternative to `source_file`).

### scramble_spans()

Reorder chunks based on `chunk_order` and ensure tags are opened and closed correctly.

**Parameters**:

- `span_positions`: Original span positions, typically obtained from [`gather_annotations()`](#gather_annotations).
- `chunk_name`: Name of the annotation to reorder.
- `chunk_order`: Annotation specifying the new order of the chunks.

## Install/Uninstall Utils

`sparv.api.util.install` provides functions for installing and uninstalling corpora, either locally or remotely.

### install_path()

Transfer a file or the contents of a directory to a target destination, optionally on a different host.

**Parameters**:

- `source_path`: Path to the local file or directory to sync. If a directory is specified, its contents are synced, not
   the directory itself, and any extraneous files in destination directories are deleted.
- `host`: Remote host to install to. Set to `None` to install locally.
- `target_path`: Path to the target file or directory.

### uninstall_path()

Remove a file or directory, optionally on a different host.

**Parameters**:

- `path`: Path to the file or directory to remove.
- `host` (optional): Remote host where the file or directory is located.

### install_mysql()

Insert tables and data from one or more SQL files into a local or remote MySQL database.

**Parameters**:

- `host`: The remote host to install to. Set to `None` to install locally.
- `db_name`: The name of the database.
- `sqlfile`: The path to a SQL file, or a list of paths to multiple SQL files.

### install_mysql_dump()

Copy selected tables, including their data, from a local MySQL database to a remote one.

**Parameters**:

- `host`: The remote host to install to.
- `db_name`: The name of the remote database.
- `tables`: The names of the SQL tables to be copied, separated by spaces.

## System Utils

`sparv.api.util.system` provides functions for managing processes, creating directories, and more.

### call_binary()

Execute a binary with specified `arguments` and `stdin`, returning a tuple `(stdout, stderr)`.

**Parameters**:

- `name`: The binary to execute (can include absolute or relative path). Accepts a string or a list of strings, using
  the first found binary.
- `arguments`: Arguments to pass to the binary. Defaults to `()`.
- `stdin`: Input to pass to the binary's stdin. Defaults to `""`.
- `raw_command`: A raw command string to execute through the shell. Use only if necessary. Defaults to `None`.
- `search_paths`: Additional paths to search for the binary, besides the environment variable PATH. Defaults to `()`.
- `encoding`: Encoding for `stdin`. Defaults to `None`.
- `verbose`: If `True`, pipes all stderr output to the terminal and returns an empty string for stderr. Defaults to
  `False`.
- `use_shell`: If `True`, executes the binary through the shell. Automatically set to `True` when using `raw_command`.
  Defaults to `False`.
- `allow_error`: If `False`, raises an exception if stderr is not empty and logs stderr and stdout. Defaults to `False`.
- `return_command`: If `True`, returns the process. Defaults to `False`.

### call_java()

Execute a Java program using a specified jar file, command line arguments, and stdin input. Returns a tuple `(stdout,
stderr)`.

**Parameters**:

- `jar`: The name of the jar file to execute.
- `arguments`: A list of arguments to pass to the Java program. Defaults to `()`.
- `options`: A list of Java options to include in the call. Defaults to `[]`.
- `stdin`: Input to pass to the program's stdin. Defaults to `""`.
- `search_paths`: Additional paths to search for the Java binary, in addition to the environment variable PATH. Defaults
  to `()`.
- `encoding`: The encoding to use for `stdin`. Defaults to `None`.
- `verbose`: If `True`, pipes all stderr output to the terminal and returns an empty string for stderr. Defaults to
  `False`.
- `return_command`: If `True`, returns the process instead of executing it. Defaults to `False`.

### clear_directory()

Create a new directory at the specified path. If the directory already exists, remove all its contents before creating a
new one.

**Parameters**:

- `path`: The path where the directory should be created.

### find_binary()

Locate the binary for a given program. Returns the path to the binary, or `None` if not found.

**Parameters**:

- `name`: The name of the binary, either as a string or a list of strings with alternative names.
- `search_paths`: A list of additional paths to search, besides those in the environment variable PATH.
- `executable`: If `False`, does not fail when the binary is not executable. Defaults to `True`.
- `allow_dir`: If `True`, allows the target to be a directory instead of a file. Defaults to `False`.
- `raise_error`: If `True`, raises an error if the binary could not be found. Defaults to `False`.

### gpus()

Retrieve a list of available NVIDIA GPUs, sorted by free memory in descending order. If the function fails, it returns
`None`. This function requires the `nvidia-smi` utility to be installed.

**Arguments:**

- `reorder`: If `True` (default), the GPUs are renumbered according to the order specified in the environment
    variable `CUDA_VISIBLE_DEVICES`. For example, if `CUDA_VISIBLE_DEVICES=1,0`, and the GPUs with most free memory are
    0, 1, the function will return `[1, 0]`. This is needed for PyTorch, which uses the GPU indices as specified in
    `CUDA_VISIBLE_DEVICES`, not the actual GPU indices. In the previous example, PyTorch would consider GPU 1 as GPU 0
    and GPU 0 as GPU 1.

### kill_process()

Terminate a process, ignoring any errors if the process is already terminated.

**Parameters**:

- `process`: The process to be terminated.

### rsync()

Synchronize files and directories using rsync. When syncing directories, any extra files in the destination directories
are removed.

**Parameters**:

- `local`: Path to the local file or directory to be synchronized.
- `host`: The remote host to sync to. Set to `None` to perform a local sync.
- `remote`: Path to the target file or directory.

## Tag Sets

The `sparv.api.util.tagsets` subpackage includes modules with functions and objects for tag set conversions.

### tagmappings.join_tag()

Convert a complex SUC or SALDO tag record into a string.

**Parameters**:

- `tag`: The tag to convert, which can be a dictionary (`{'pos': pos, 'msd': msd}`) or a tuple (`(pos, msd)`).
- `sep`: The separator to use. Default: "."

### tagmappings.mappings

Mappings of part-of-speech tags between different tag sets.

### pos_to_upos()

Map POS tags to Universal Dependency POS tags. This function only works if there is a conversion function in
`util.tagsets.pos_to_upos` for the specified language and tag set.

**Parameters**:

- `pos`: The part-of-speech tag to convert.
- `lang`: The language code.
- `tagset`: The name of the tag set to which `pos` belongs.

### tagmappings.split_tag()

Split a SUC or Saldo tag string ('X.Y.Z') into a tuple ('X', 'Y.Z'), where 'X' is the part of speech and 'Y', 'Z', etc.,
are morphological features (i.e., MSD tags).

**Parameters**:

- `tag`: The tag string to split into a tuple.
- `sep`: The separator to split on. Default: "."

### suc_to_feats()

Convert SUC MSD tags into a UCoNNL feature list (universal morphological features). Returns a list of universal
features.

**Parameters**:

- `pos`: The SUC part-of-speech tag.
- `msd`: The SUC MSD tag.
- `delim`: The delimiter separating the features in `msd`. Default: "."

### tagmappings.tags

Different sets of part-of-speech tags.

## Miscellaneous Utils

`sparv.api.util.misc` provides miscellaneous util functions.

<!-- ### chain() -->

### cwbset()

Convert an iterable object into a set formatted for Corpus Workbench.

**Parameters**:

- `values`: An iterable containing string values.
- `delimiter`: Character used to separate elements in the resulting set. Default: "|"
- `affix`: Character that encloses the resulting set. Default: "|"
- `sort`: If `True`, sorts the values. Default: `False`
- `maxlength`: Maximum length of the resulting set in characters. Default: 4095
- `encoding`: Encoding of the `values`. Default: "UTF-8"

### dump_yaml()

Convert a dictionary to a YAML formatted string.

**Parameters**:

- `data`: The dictionary to convert.
- `resolve_alias`: If `True`, replaces aliases with their anchor's content. Default: `False`.
- `sort_keys`: If `True`, sorts the keys alphabetically. Default: `False`.
- `indent`: The number of spaces to use for indentation. Default: `2`.

### parse_annotation_list()

Parse a list of annotation names and their optional export names, returning a list of tuples. Each item in the list is
split into a tuple by the string ' as '. Each tuple will contain two elements. If ' as ' is not present in the string,
the second element will be `None`.

If the list of annotation names includes the element '...', all annotations from `all_annotations` will be included in
the result, except those explicitly excluded in the list of annotations by being prefixed with 'not '.

**Parameters**:

- `annotation_names`: A list of annotation names.
- `all_annotations`: A list of all possible annotations. Default: `[]`
- `add_plain_annotations`: If `True`, plain annotations (without attributes) will be added if needed. Set to `False` if
  annotation names may include classes or config variables. Default: `True`

### PickledLexicon

A class for reading a basic pickled lexicon and looking up keys.

**Parameters**:

- `picklefile`: A `pathlib.Path` or `Model` object pointing to the pickled lexicon.
- `verbose`: If `True`, logs status updates while reading the lexicon. Default: `True`.

**Methods**:

- `lookup(key, default=set())`: Look up `key` in the lexicon. Returns `default` if `key` is not found.

### remove_control_characters()

Eliminate control characters from the given `text`, while retaining those specified in `keep`.

**Parameters**:

- `text`: The string from which to remove control characters.
- `keep`: A list of control characters to retain. Default: `["\n", "\t", "\r"]`

### remove_formatting_characters()

Eliminate formatting characters from the given `text`, while retaining those specified in `keep`.

**Parameters**:

- `text`: The string from which to remove formatting characters.
- `keep`: A list of formatting characters to retain. Default: `[]`

### set_to_list()

Convert a set-formatted string into a list.

**Parameters**:

- `setstring`: The string to convert into a list. The string should be enclosed with `affix` characters and have
  elements separated by `delimiter`.
- `delimiter`: The character used to separate elements in `setstring`. Default: "|"
- `affix`: The character that encloses `setstring`. Default: "|"

### test_lexicon()

Validate a lexicon by checking if specific test words are present as keys. This function takes a dictionary (lexicon)
and a list of test words, printing the value associated with each test word.

**Parameters**:

- `lexicon`: A dictionary representing the lexicon.
- `testwords`: An iterable of strings, each expected to be a key in the `lexicon`.

## Error Messages and Logging

The `SparvErrorMessage` exception and `get_logger` function are essential components of the Sparv pipeline. Unlike other
utilities mentioned on this page, they are located directly under `sparv.api`.

### SparvErrorMessage

This exception class is used to halt the pipeline, while notifying users of errors in a user-friendly manner without
displaying a traceback. Its usage is detailed in the [Writing Sparv Plugins](writing-sparv-plugins.md#error-messages)
section.

> [!NOTE]
> When raising this exception in a Sparv module, only the `message` argument should be used.

**Parameters**:

- `message`: The error message to display.
- `module`: The name of the module where the error occurred (optional, not used in Sparv modules). Default: ""
- `function`: The name of the function where the error occurred (optional, not used in Sparv modules).
  Default: ""

### get_logger()

This function retrieves a logger that is a child of `sparv.modules`. Its usage is explained in the [Writing Sparv
Plugins](writing-sparv-plugins.md#logging) section.

**Parameters**:

- `name`: The name of the current module (usually `__name__`)
