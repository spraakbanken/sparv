# Sparv Processors

Sparv is made up of a series of processors, each of which performs a specific task. These processors are
implemented as Python functions that are decorated with one of the Sparv decorators. The decorators are used to
register the functions within the Sparv pipeline and to provide metadata about the function, such as its description,
inputs, outputs, and configuration options. The input and output annotations of the functions are used to build a
dependency graph, which is used to determine the order in which the functions should be executed to process the corpus
data.

The different types of processors are: annotators, importers, exporters, installers, uninstallers, model builders, and
wizards. Below is a description of each type of processor and the decorators used to create them.

The only required argument for all decorators (except for `@wizard` ) is `description`, which is a string explaining
what the function does. This description is used for displaying help texts in the CLI. All other arguments are optional.

## @annotator

A function decorated with `@annotator` processes input data (such as models, annotations like tokens, sentences, parts
of speech, etc.) and generates new annotations.

**Parameters**:

- `name`: An optional name to use instead of the function name.
- `description`: A description of the annotator, used for displaying help texts in the CLI. The first line should be a
  short summary of what the annotator does. Optionally, a longer description can be added below the first line,
  separated by a blank line.
- `config`: A list of `Config` instances defining configuration options for the annotator.
- `language`: A list of supported languages. If no list is provided, all languages are supported.
- `priority`: Functions with higher priority (higher number) will be preferred when scheduling which functions to run.
  The default priority is 0.
- `order`: If multiple annotators produce the same output, this integer value helps determine which to try to use first.
  A lower number indicates higher priority.
- `wildcards`: A list of wildcards used in the annotator function's arguments.
- `preloader`: A reference to a preloader function, used to preload models or processes.
- `preloader_params`: A list of parameter names for the annotator, which will be used as arguments for the preloader.
- `preloader_target`: The name of the annotator parameter that should receive the return value of the preloader.
- `preloader_cleanup`: A reference to an optional cleanup function, which will be executed after each annotator use.
- `preloader_shared`: Set to `False` if the preloader result should not be shared among preloader processes.

**Example:**

```python
@annotator(
    "Part-of-speech tags and baseforms from TreeTagger",
    language=["bul", "est", "fin", "lat", "nld", "pol", "ron", "slk", "deu", "eng", "fra", "spa", "ita", "rus"],
    config=[
        Config("treetagger.binary", "tree-tagger", description="TreeTagger executable"),
        Config("treetagger.model", "treetagger/[metadata.language].par", description="Path to TreeTagger model"),
    ],
)
def annotate(
    lang: Language = Language(),
    model: Model = Model("[treetagger.model]"),
    tt_binary: Binary = Binary("[treetagger.binary]"),
    out_upos: Output = Output("<token>:treetagger.upos", cls="token:upos", description="Part-of-speeches in UD"),
    out_pos: Output = Output("<token>:treetagger.pos", cls="token:pos", description="Part-of-speeches from TreeTagger"),
    out_baseform: Output = Output("<token>:treetagger.baseform", description="Baseforms from TreeTagger"),
    word: Annotation = Annotation("<token:word>"),
    sentence: Annotation = Annotation("<sentence>"),
):
    ...
```

## @importer

A function decorated with `@importer` is responsible for importing corpus files in a specific file format. Its task is
to read a corpus file, extract the corpus text and any existing markup (if applicable), and write annotation files for
the corpus text and markup.

Importers do not use the `Output` class to specify their outputs. Instead, outputs are listed using the `outputs`
argument of the decorator. Any output that needs to be used as explicit input by another part of the pipeline must be
listed here, although additional unlisted outputs may also be created.

Two outputs are implicit (and thus not listed in `outputs`) but required for every importer: the corpus text, saved
using the `Text` class, and a list of the annotations created from existing markup, saved using the `SourceStructure`
class.

**Parameters**:

- `description`: A description of the importer, used for displaying help texts in the CLI. The first line should be a
  short summary of what the importer does. Optionally, a longer description can be added below the first line, separated
  by a blank line.
- `file_extension`: The file extension of the type of source this importer handles, e.g., "xml" or "txt".
- `name`: An optional name to use instead of the function name.
- `outputs`: A list of annotations and attributes that the importer is guaranteed to generate. This may also be a
  `Config` instance referring to such a list. The importer may generate more outputs than listed, but only the
  annotations listed here will be available to use as input for annotator functions.
- `config`: A list of `Config` instances defining configuration options for the importer.

**Example:**

```python
@importer("TXT import", file_extension="txt", outputs=["text"])
def parse(
    source_file: SourceFilename = SourceFilename(),
    source_dir: Source = Source(),
    prefix: str = "",
    encoding: str = util.constants.UTF8,
    normalize: str = "NFC",
) -> None:
    ...
```

## @exporter

The `@exporter` decorator is used to create functions that generate final outputs, often referred to as exports. These
outputs typically combine information from multiple annotations into a single file. The output produced by an exporter
is generally not used as input for any other module. An export can consist of any kind of data, such as a frequency
list, XML files, or a database dump. It can create one file per source file, combine information from all source files
into a single output file, or follow any other structure as needed.

**Parameters**:

- `description`: A brief summary of what the exporter does. This is used for displaying help texts in the CLI.
  Optionally, a longer description can be added below the first line, separated by a blank line.
- `name`: An optional name to use instead of the function name.
- `config`: A list of `Config` instances defining configuration options for the exporter.
- `language`: A list of supported languages. If no list is provided, all languages are supported.
- `priority`: Functions with higher priority (higher number) will be preferred when scheduling which functions to run.
  The default priority is 0.
- `order`: If multiple exporters produce the same output, this integer value helps determine which to try to use first.
  A lower number indicates higher priority.
- `abstract`: Set to `True` if this exporter does not produce any output.

**Example:**

```python
@exporter(
    "Corpus word frequency list (withouth Swedish annotations)",
    order=2,
    config=[
        Config("stats_export.delimiter", default="\t", description="Delimiter separating columns"),
        Config(
            "stats_export.cutoff",
            default=1,
            description="The minimum frequency a word must have in order to be included in the result",
        ),
    ],
)
def freq_list_simple(
    corpus: Corpus = Corpus(),
    source_files: AllSourceFilenames = AllSourceFilenames(),
    word: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token:word>"),
    pos: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token:pos>"),
    baseform: AnnotationAllSourceFiles = AnnotationAllSourceFiles("<token:baseform>"),
    out: Export = Export("stats_export.frequency_list/stats_[metadata.id].csv"),
    delimiter: str = Config("stats_export.delimiter"),
    cutoff: int = Config("stats_export.cutoff"),
):
    ...
```

## @installer

The `@installer` decorator is used to create functions that deploy the corpus or related files to a remote location. For
example, it can copy XML output to a web server or insert SQL data into a database.

Every installer must create a marker of the type `OutputMarker` at the end of a successful installation. Simply call the
`write()` method on the marker to create the required marker.

It is recommended that an installer removes any related uninstaller's marker to enable uninstallation. Use the
`MarkerOptional` class to refer to the uninstaller's marker without triggering an unnecessary installation.

**Parameters**:

- `description`: A brief summary of what the installer does. This is used for displaying help texts in the CLI.
  Optionally, a longer description can be added below the first line, separated by a blank line.
- `name`: An optional name to use instead of the function name.
- `config`: A list of `Config` instances defining configuration options for the installer.
- `language`: A list of supported languages. If no list is provided, all languages are supported.
- `priority`: Functions with higher priority (higher number) will be preferred when scheduling which functions to run.
  The default priority is 0.
- `uninstaller`: The name of the related uninstaller.

**Example:**

```python
@installer(
    "Copy compressed XML to remote host",
    config=[
        Config("xml_export.export_host", description="Remote host to copy XML export to."),
        Config("xml_export.export_path", description="Path on remote host to copy XML export to."),
    ],
)
def install(
    corpus: Corpus = Corpus(),
    xmlfile: ExportInput = ExportInput("xml_export.combined/[metadata.id].xml.bz2"),
    out: OutputMarker = OutputMarker("xml_export.install_export_pretty_marker"),
    export_path: str = Config("xml_export.export_path"),
    host: Optional[str] = Config("xml_export.export_host"),
):
    ...
```

## @uninstaller

The `@uninstaller` decorator is used to create functions that undo the actions performed by an installer, such as
removing corpus files from a remote location or deleting corpus data from a database.

Every uninstaller must create a marker of the type `OutputMarker` at the end of a successful uninstallation. Simply call
the `write()` method on the marker to create the required marker.

It is recommended that an uninstaller removes any related installer's marker to enable re-installation. Use the
`MarkerOptional` class to refer to the installer's marker without triggering an unnecessary installation.

**Parameters**:

- `description`: A brief summary of what the uninstaller does. This is used for displaying help texts in the CLI.
  Optionally, a longer description can be added below the first line, separated by a blank line.
- `name`: An optional name to use instead of the function name.
- `config`: A list of `Config` instances defining configuration options for the uninstaller.
- `language`: A list of supported languages. If no list is provided, all languages are supported.
- `priority`: Functions with higher priority (higher number) will be preferred when scheduling which functions to run.
  The default priority is 0.

**Example:**

```python
@uninstaller(
    "Remove compressed XML from remote host",
    config=[
        Config("xml_export.export_host", description="Remote host to remove XML export from."),
        Config("xml_export.export_path", description="Path on remote host to remove XML export from."),
    ],
)
def uninstall(
    corpus: Corpus = Corpus(),
    xmlfile: ExportInput = ExportInput("xml_export.combined/[metadata.id].xml.bz2"),
    out: OutputMarker = OutputMarker("xml_export.uninstall_export_pretty_marker"),
    export_path: str = Config("xml_export.export_path"),
    host: Optional[str] = Config("xml_export.export_host"),
):
    ...
```

## @modelbuilder

The `@modelbuilder` decorator is used to create functions that set up models that other Sparv processors (typically
annotators) rely on. Setting up a model might involve tasks such as downloading a file, unzipping it, converting it to a
different format, and saving it in Sparv's data directory. Models are generally not specific to a single corpus; once a
model is set up on your system, it will be available for any corpus.

**Parameters**:

- `description`: A brief summary of what the model builder does, used for displaying help texts in the CLI. The first
  line should be a short summary, with an optional longer description below, separated by a blank line.
- `name`: An optional name to use instead of the function name.
- `config`: A list of `Config` instances defining configuration options for the model builder.
- `language`: A list of supported languages. If no list is provided, all languages are supported.
- `priority`: Functions with higher priority (higher number) will be preferred when scheduling which functions to run.
  The default priority is 0.
- `order`: If multiple model builders produce the same output, this integer value helps determine which to try to use
  first. A lower number indicates higher priority.

**Example:**

```python
@modelbuilder("Sentiment model (SenSALDO)", language=["swe"])
def build_model(out: ModelOutput = ModelOutput("sensaldo/sensaldo.pickle")):
   ...
```

## @wizard

A function decorated with `@wizard` is used to generate questions for the corpus config wizard.

> [!NOTE]
> The wizard functionality is deprecated and will be removed in a future version of Sparv.

**Parameters**:

- `config_keys`: a list of config keys to be set or changed by this function.
- `source_structure`: Set to `True` if the function needs access to a `SourceStructureParser` instance (the one holding
  information on the structure of the source files). Default: `False`

**Example:**

```python
@wizard(["export.source_annotations"], source_structure=True)
def import_wizard(answers, structure: SourceStructureParser):
    ...
```
