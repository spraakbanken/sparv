# Sparv Classes

Sparv classes are used to represent various types of data in Sparv, such as source files, models, and input and output
annotations. By using Sparv classes in the signatures of [processors](sparv-decorators.md), Sparv knows the inputs and
outputs of each processor and can build a dependency graph to determine the order in which processors should be run to
produce the desired output. Additionally, Sparv classes provide useful methods for reading and writing annotations,
allowing annotators to handle annotation files without needing to understand Sparv's internal data format. Below is a
list of all available Sparv classes, including their parameters, properties, and public methods.

## AllSourceFilenames

This class provides an iterable containing the names of all source files. It is commonly used by exporter functions that
need to combine annotations from multiple source files.

## Annotation

This class represents a regular annotation tied to a single source file. It is used when an annotation is required as
input for a function, for example, `Annotation("<token:word>")`.

**Parameters**:

- `name`: The name of the annotation.
- `source_file`: The name of the source file.

**Properties**:

- `has_attribute`: Return `True` if the annotation has an attribute.
- `annotation_name`: Retrieve the annotation name (excluding any attribute name).
- `attribute_name`: Retrieve the attribute name (excluding the annotation name).
- `size`: Number of values in the annotation.

**Methods**:

- `split()`: Split the name into annotation name and attribute.
- `exists()`: Return `True` if the annotation file exists.
- `remove()`: Remove the annotation file.
- `read()`: Yield each line from the annotation.
- `read_spans(decimals=False, with_annotation_name=False)`: Yield the spans of the annotation.
- `read_text()`: Yield the underlying source text of the annotation.
- `read_attributes(annotations: Union[list[BaseAnnotation], tuple[BaseAnnotation, ...]], with_annotation_name=False)`:
  Yield tuples of multiple attributes on the same annotation.
- `get_children(child: BaseAnnotation, orphan_alert=False)`: Return two lists. The first list is a list of lists. Each
  inner list corresponds to a parent and contains indices that point to elements in the child annotation. The second
  list contains indices in the child annotation that have no parent. Both lists are sorted according to their position
  in the source file.
- `get_child_values(child: BaseAnnotation, append_orphans=False, orphan_alert=False)`: Return an iterator with one
  element for each parent. Each element is an iterator of values in the child annotation. If `append_orphans` is `True`,
  the last element is an iterator of orphans.
- `get_parents(parent: BaseAnnotation, orphan_alert=False)`: Return a list of indices in the parent annotation for each
  child. Returns `None` if no parent is found.
- `read_parents_and_children(parent, child)`: Read parent and child annotations, reorders them according to span
  position, but keeps original index information.
- `create_empty_attribute()`: Return a list filled with `None` of the same size as this annotation.
- `get_size()`: Return the number of values. **Note:** This method is deprecated and will be removed in a future version of
  Sparv. Use the `size` property instead.

## AnnotationAllSourceFiles

Like [`Annotation`](#annotation), this class represents a regular annotation, but is used as input to an annotator
to require the specified annotation for *every source file* in the corpus.
By calling an instance of this class with a source file name as an argument, you can get an instance of `Annotation`
for that source file.

**Parameters**:

- `name`: The name of the annotation.

**Properties**:

- `has_attribute`: Return `True` if the annotation has an attribute.
- `annotation_name`: Retrieve the annotation name (excluding any attribute name).
- `attribute_name`: Retrieve the attribute name (excluding the annotation name).

**Methods**:

> [!NOTE]
> All methods of this class are deprecated and will be removed in a future version of Sparv. Instead, create an
> instance of `Annotation` by passing a source file name as an argument, and use the methods of the `Annotation` class.

## AnnotationCommonData

Like [`AnnotationData`](#annotationdata), this class represents an annotation with arbitrary data when used as input to
an annotator. However, `AnnotationCommonData` is used for data that applies to the entire corpus, not tied to a specific
source file.

**Parameters**:

- `name`: The name of the annotation.

**Properties**:

- `annotation_name`: Retrieve the annotation name (excluding any attribute name).
- `attribute_name`: Retrieve the attribute name (excluding the annotation name).

**Methods**:

- `split()`: Split the name into annotation name and attribute.
- `read()`: Read arbitrary corpus-level string data from the annotation file.
- `exists()`: Return `True` if the annotation file exists.
- `remove()`: Remove the annotation file.

## AnnotationName

Use this class when only the name of an annotation is needed, not the actual data. The annotation will not be added as a
prerequisite for the annotator, meaning that using `AnnotationName` will not automatically trigger the creation of the
referenced annotation.

**Parameters**:

- `name`: The name of the annotation.
- `source_file`: The name of the source file.

## AnnotationData

This class represents an annotation holding arbitrary data, i.e., data that is not tied to spans in the corpus text. It
is used as input to an annotator.

**Parameters**:

- `name`: The name of the annotation.
- `source_file`: The name of the source file.

**Properties**:

- `has_attribute`: Return `True` if the annotation has an attribute.
- `annotation_name`: Retrieve the annotation name (excluding any attribute name).
- `attribute_name`: Retrieve the attribute name (excluding the annotation name).

**Methods**:

- `split()`: Split the name into annotation name and attribute.
- `exists()`: Return `True` if the annotation file exists.
- `remove()`: Remove the annotation file.
- `read(source_file: Optional[str] = None)`: Read arbitrary string data from the annotation file.

## AnnotationDataAllSourceFiles

Similar to [`AnnotationData`](#annotationdata), this class is used for annotations holding arbitrary data, but it is
used as input to an annotator to require the specified annotation for *every source file* in the corpus. By calling an
instance of this class with a source file name as an argument, you can get an instance of `AnnotationData` for that
source file.

**Parameters**:

- `name`: The name of the annotation.

**Properties**:

- `annotation_name`: Retrieve the annotation name (excluding any attribute name).
- `attribute_name`: Retrieve the attribute name (excluding the annotation name).

**Methods**:

> [!NOTE]
> All methods of this class are deprecated and will be removed in a future version of Sparv. Instead, create an
> instance of `AnnotationData` by passing a source file name as an argument, and use the methods of the `AnnotationData`
> class.

## Binary

This class holds the path to a binary executable. The path can be either the name of a binary in the system's PATH, a
full path to a binary, or a path relative to the Sparv data directory. It is often used to define a prerequisite for an
annotator function.

**Parameters**:

- Path to the binary executable.

## BinaryDir

This class holds the path to a directory containing executable binaries. The path can be either an absolute path or a
path relative to the Sparv data directory.

**Parameters**:

- Path to the directory containing executable binaries.

## Config

This class represents a configuration key and optionally its default value. You can specify the datatype and allowed
values, which will be used for validating the config and generating the Sparv config JSON schema.

For further information on how to use this class, see the [Config Parameters](config-parameters.md) page.

**Parameters**:

- `name`: The configuration key name.
- `default`: The optional default value of the configuration key.
- `description`: A mandatory description of the configuration key.
- `datatype`: A type specifying the allowed datatype(s). Supported types are `int`, `float`, `str`, `bool`, `None`,
  `type(None)`, `list`, and `dict`. For `list` and `dict`, you can specify the allowed types for the elements by using
   type arguments, like `list[str]` or `dict[str, int]`. More complex types (e.g., further nesting) than these are not
   supported. `type(None)` is used to allow `None` as a value. `None` is the default value, and means that any datatype
    is allowed.
- `choices`: An iterable of valid choices, or a function that returns such an iterable.
- `pattern`: A regular expression matching valid values (only for the datatype `str`).
- `min`: A `float` representing the minimum numeric value.
- `max`: A `float` representing the maximum numeric value.
- `const`: Restrict the value to a single value.
- `conditions`: A list of `Config` objects with conditions that must also be met.

## Corpus

Represents the name (ID) of the corpus.

## SourceFilename

Represents the name of a source file.

## Export

Represents an export file, used to define the output of an exporter function.

**Parameters**:

- The export directory and filename pattern (e.g., `"xml_export.pretty/[xml_export.filename]"`). The export
  directory must include the module name as a prefix or be equal to the module name.

## ExportAnnotations

An iterable containing annotations to be included in the export, as specified in the corpus configuration.
When using this class, annotation files for the current source file are automatically added as dependencies.

**Parameters**:

- `config_name`: The configuration variable specifying which annotations to include.

## ExportAnnotationsAllSourceFiles

An iterable containing annotations to be included in the export, as specified in the corpus configuration.
When using this class, annotation files for *all* source files will automatically be added as dependencies.

**Parameters**:

- `config_name`: The configuration variable specifying which annotations to include.

## ExportAnnotationNames

An iterable containing annotations to be included in the export, as specified in the corpus configuration. Unlike
`ExportAnnotations`, using this class will not add the annotations as dependencies.

**Parameters**:

- `config_name`: The configuration variable specifying which annotations to include.

## ExportInput

Represents the export directory and filename pattern used as input. Use this class when you need export files as input
for another function.

**Parameters**:

- `val`: The export directory and filename pattern (e.g., `"xml_export.pretty/[xml_export.filename]"`).
- `all_files`: Set to `True` to include exports for all source files. Default is `False`.

## HeaderAnnotations

An iterable containing header annotations from the source to be included in the export, as specified in the
corpus configuration.

**Parameters**:

- `config_name`: The configuration variable that specifies which header annotations to include.

## HeaderAnnotationsAllSourceFiles

An iterable containing header annotations from all source files to be included in the export, as specified in the corpus
configuration. Unlike `HeaderAnnotations`, this class ensures that the header annotations file (created using `Headers`)
for *every* source file is added as a dependency.

**Parameters**:

- `config_name`: The configuration variable specifying which source annotations to include.

## Headers

Represents a list of header annotation names for a given source file, used as output for importers.

**Parameters**:

- The name of the source file.

**Methods**:

- `read()`: Read the headers file and return a list of header annotation names.
- `write(header_annotations: list[str])`: Write the headers file with the provided list of header annotation names.
- `exists()`: Return `True` if the headers file exists for this source file.
- `remove()`: Remove the headers file.

## Language

An instance of this class contains information about the language of the corpus. This information is retrieved from the
corpus configuration and is specified using an ISO 639-1 language code.

## Marker

Similar to `AnnotationCommonData`, but typically without any actual data. Used as input. Markers are used to make sure
that something has been executed. Created using `OutputMarker`.

**Parameters**:

- `name`: The name of the marker.

**Methods**:

- `read()`: Read arbitrary corpus-level string data from the marker file.
- `exists()`: Return `True` if the marker file exists.
- `remove()`: Remove the marker file.

## MarkerOptional

Same as `Marker`, but if the marker file doesn't exist, it won't be created. This is mainly used to get a reference to a
marker that may or may not exist, to be able to remove markers from connected (un)installers without triggering the
connected (un)installation. Otherwise, running an uninstaller without first having run the installer would needlessly
trigger the installation first.

**Parameters**:

- `name`: The name of the marker.

**Methods**:

- `read()`: Read arbitrary corpus-level string data from the marker file.
- `exists()`: Return `True` if the marker file exists.
- `remove()`: Remove the marker file.

## Model

Represents a path to a model file. The path can be either an absolute path, a relative path, or a path relative to the
Sparv model directory. Typically used as input to annotator functions.

**Parameters**:

- `name`: The path to the model file.

**Properties**:

- `path`: Get the path to the model file as a `pathlib.Path` object.

**Methods**:

- `write(data)`: Write arbitrary string data to the model file.
- `read()`: Read arbitrary string data from the model file.
- `write_pickle(data, protocol=-1)`: Dump `data` to the model file in pickle format.
- `read_pickle()`: Read pickled data from the model file.
- `download(url: str)`: Download the file from `url` and save it to the model path.
- `unzip()`: Unzip the zip file in same directory as the model file.
- `ungzip(out: str)`: Unzip the gzip file in same directory as the model file.
- `remove(raise_errors: bool = False)`: Remove the model file from disk. If `raise_errors` is `True`, raise an error if
  the file cannot be removed (e.g., if it does not exist).

## ModelOutput

Same as [`Model`](#model), but used as the output of a model builder.

**Parameters**:

- `name`: The name of the annotation.
- `description`: An optional description.

**Properties**:

- `path`: Get the path to the model file as a `pathlib.Path` object.

**Methods**:

- `write(data)`: Write arbitrary string data to the model file.
- `read()`: Read arbitrary string data from the model file.
- `write_pickle(data, protocol=-1)`: Dump `data` to the model file in pickle format.
- `read_pickle()`: Read pickled data from the model file.
- `download(url: str)`: Download the file from `url` and save it to the model path.
- `unzip()`: Unzip the zip file in same directory as the model file.
- `ungzip(out: str)`: Unzip the gzip file in same directory as the model file.
- `remove(raise_errors: bool = False)`: Remove the model file from disk. If `raise_errors` is `True`, raise an error if
  the file cannot be removed (e.g., if it does not exist).

## Output

Represents a regular annotation or attribute used as output from an annotator function.

**Parameters**:

- `name`: The name of the annotation.
- `cls`: The annotation class of the output.
- `description`: An optional description.
- `source_file`: The name of the source file.

**Methods**:

- `split()`: Split the name into annotation name and attribute.
- `write(values, source_file: Optional[str] = None)`: Write the annotation to a file, overwriting any existing
  annotation. `values` should be a list of values.
- `exists()`: Return `True` if the annotation file exists.
- `remove()`: Remove the annotation file.

## OutputAllSourceFiles

Similar to [`Output`](#output), this class represents a regular annotation or attribute used as output, but it is used
when output should be produced for *every source file* in the corpus. By calling an instance of this class with a source
file name as an argument, you can get an instance of `Output` for that source file.

**Parameters**:

- `name`: The name of the annotation.
- `cls`: The annotation class of the output.
- `description`: An optional description.

**Methods**:

> [!NOTE]
> All methods of this class are deprecated and will be removed in a future version of Sparv. Instead, create an
> instance of `Output` by passing a source file name as an argument, and use the methods of the `Output` class.

## OutputCommonData

Similar to [`OutputData`](#outputdata), but for a data annotation that applies to the entire corpus.

**Parameters**:

- `name`: The name of the annotation.
- `cls`: The annotation class of the output.
- `description`: An optional description.

**Methods**:

- `split()`: Split the name into annotation name and attribute.
- `write(value)`: Write arbitrary corpus-level string data to the annotation file.
- `exists()`: Return `True` if the annotation file exists.
- `remove()`: Remove the annotation file.

## OutputData

Represents an annotation holding arbitrary data that is used as output. This data is not tied to spans in the corpus
text.

**Parameters**:

- `name`: The name of the annotation.
- `cls`: The annotation class of the output.
- `description`: An optional description.
- `source_file`: The name of the source file.

**Methods**:

- `split()`: Split the name into annotation name and attribute.
- `write(value)`: Write arbitrary corpus-level string data to the annotation file.
- `exists()`: Return `True` if the annotation file exists.
- `remove()`: Remove the annotation file.

## OutputDataAllSourceFiles

Similar to [`OutputData`](#outputdata), this class is used for output annotations holding arbitrary data, but it is used
when output should be produced for *every source file* in the corpus. By calling an instance of this class with a source
file name as an argument, you can get an instance of `OutputData` for that source file.

**Parameters**:

- `name`: The name of the annotation.
- `cls`: The annotation class of the output.
- `description`: An optional description.

**Methods**:

> [!NOTE]
> All methods of this class are deprecated and will be removed in a future version of Sparv. Instead, create an
> instance of `OutputData` by passing a source file name as an argument, and use the methods of the `OutputData` class.

## OutputMarker

Similar to `OutputCommonData`, but typically without any actual data. Markers are used to indicate that something has
been executed, often by functions that don't produce a natural output, such as installers and uninstallers.

**Parameters**:

- `name`: The name of the marker.
- `cls`: The annotation class of the output.
- `description`: An optional description.

**Methods**:

- `write(value = "")`: Write arbitrary corpus-level string data to the marker file. Usually called without arguments.
- `exists()`: Return `True` if the marker file exists.
- `remove()`: Remove the marker file.

## Source

Represents the path to the directory containing input files.

**Parameters**:

- Path to the directory containing input files.

**Methods**:

- `get_path(source_file: SourceFilename, extension: str)`: Retrieve the path to a specific source file.

## SourceAnnotations

An iterable containing source annotations to include in the export, as specified in the corpus configuration.

**Parameters**:

- `config_name`: The configuration variable specifying which source annotations to include.

## SourceAnnotationsAllSourceFiles

An iterable containing source annotations to include in the export, as specified in the corpus configuration. Unlike
`SourceAnnotations`, this class ensures that the source annotations structure file (created using `SourceStructure`) for
*every* source file is added as a dependency.

**Parameters**:

- `config_name`: The configuration variable specifying which source annotations to include.

## SourceStructure

Represents all annotation names available in a source file.

**Parameters**:

- The name of the source file.

**Methods**:

- `read()`: Read the structure file.
- `write(structure)`: Sort and write the annotation names to the structure file.

## SourceStructureParser

Abstract class to be implemented by an importer's structure parser.

> [!NOTE]
> This class is intended to be used by the wizard. The wizard functionality is going to be deprecated in a
> future version.

**Parameters**:

- `source_dir: pathlib.Path`: Path to the corpus source files.

**Methods**:

- `setup()`: Return a list of wizard dictionaries with questions needed for setting up the class. Automatically save
  answers to `self.answers`.

## Text

Represents the text content of a source file.

**Parameters**:

- `source_file`: The name of the source file.

**Methods**:

- `read()`: Retrieve the text content of the source file.
- `write(text)`: Write the provided text content to a file, overwriting any existing content. `text` should be a unicode
  string.

## Wildcard

Holds wildcard information, typically used in the `wildcards` list passed as an argument to the [`@annotator`
decorator](sparv-decorators.md#annotator), e.g.:

```python
@annotator("Number {annotation} by relative position within {parent}", wildcards=[
    Wildcard("annotation", Wildcard.ANNOTATION),
    Wildcard("parent", Wildcard.ANNOTATION)
])
```

**Parameters**:

- `name`: The name of the wildcard.
- `type`: The type of the wildcard. One of `Wildcard.ANNOTATION`, `Wildcard.ATTRIBUTE`, `Wildcard.ANNOTATION_ATTRIBUTE`,
  or `Wildcard.OTHER`. Defaults to `Wildcard.OTHER`.
- `description`: An optional description.
