# Running Sparv

This section contains a guide to running Sparv on the corpus you have prepared according to the instructions in the
previous sections. It also provides an overview of all the key commands available in Sparv.

> [!NOTE]
>
> Sparv is a command line application, and all interactions with Sparv are done through the terminal.

## Annotating Your Corpus with Sparv

Before running Sparv, make sure you have set up your corpus configuration file and placed your source files in the
source directory, as described in the previous sections.

Once you have prepared your corpus, you can start the annotation process by running the `sparv run` command from inside
the corpus directory. This command initiates the annotation process and generates all the output formats specified in
your corpus configuration file. If no output formats are specified, Sparv will use the default export format, which is
the pretty-printed XML format.

Once the annotation process is complete, the generated output files will be stored in an `export` directory within your
corpus directory. The directory structure of your corpus should look something like this:

```text
my_corpus/
├── config.yaml
├── export
│  └── xml_export.pretty
│     ├── document1_export.xml
│     ├── document2_export.xml
│     └── document3_export.xml
├── source
│  ├── document1.xml
│  ├── document2.xml
│  └── document3.xml
└── sparv-workdir
   └── ...
```

The `sparv-workdir` directory contains intermediate files used by Sparv during the annotation process. This directory is
managed by Sparv and should not be manually modified.

Keeping the `sparv-workdir` directory allows Sparv to re-run only the necessary parts of the annotation process when
changes are made to your source files. If you update a model or any other dependency, Sparv will re-run only the
annotations that depend on the updated model, including any subsequent annotations that rely on those initial
annotations. This dependency tracking mechanism ensures that you only re-run the affected parts of the annotation
process, rather than starting from scratch.

However, if you make changes to your *corpus configuration file*, you will need to perform a clean run for the changes
to take effect. Use the `sparv clean --all` command to remove intermediate files and output directories. If you only
changed the list of annotations or export formats, running `sparv clean --export` to remove the `export` directory is
sufficient.

## Sparv Command Line Interface Overview

Running `sparv` without any arguments will display all the available Sparv commands:

```text
Annotating a corpus:
   run              Annotate a corpus and generate export files
   install          Install a corpus
   uninstall        Uninstall a corpus
   clean            Remove output directories

Inspecting corpus details:
   config           Display the corpus configuration
   files            List available corpus source files that can be annotated by Sparv

Show annotation info:
   modules          List available modules and annotations
   presets          List available annotation presets
   classes          List available annotation classes
   languages        List supported languages

Setting up Sparv:
   setup            Set up the Sparv data directory
   plugins          Manage Sparv plugins
   wizard           Run config wizard to create a corpus config
   build-models     Download and build the Sparv models

Advanced commands:
   run-rule         Run specified rule(s) for creating annotations
   create-file      Create specified file(s)
   preload          Preload annotators and models
   autocomplete     Enable tab completion in bash/zsh
   schema           Print a JSON schema for the Sparv config format
```

Each command in the Sparv command line interface comes with a help text accessible via the `-h` flag. Below is an
overview of the key commands in Sparv, but for more detailed information about the parameters and options available for
each command, use the `-h` flag in the terminal.

## Annotating a Corpus

All of the following commands should be run from inside a corpus directory.

### `sparv run`

`sparv run` is the primary command for annotating a corpus. It initiates the annotation process and generates all the
output formats (or *exports*) specified under `export.default` in your config file. Alternatively, you can specify a
particular export format, for example, `sparv run csv_export:csv`. To see all available output formats for your corpus,
use `sparv run -l`. The generated output files will be stored in an `export` directory within your corpus directory.

By using the `-j` flag, you can specify the number of parallel processes to use during the annotation process. For
example, `sparv run -j 4` will run the annotation process with four parallel processes. The default value is 1.

### `sparv install`

Installing a corpus involves deploying it either locally or on a remote server. Sparv natively supports the deployment
of compressed XML exports, CWB data files, and SQL data. When you run `sparv install`, Sparv checks if all necessary
annotations are present. If any annotations are missing, Sparv will create them for you, so you don't necessarily need
to annotate the corpus beforehand. To see the available installation options, use `sparv install -l`.

### `sparv clean`

During the annotation process, Sparv creates a `sparv-workdir` directory within your corpus
directory. This directory contains intermediate files that usually speed up subsequent processing. However, if you need
to free up disk space or want to rerun all annotations from scratch, you can delete this directory by running `sparv
clean`. Additionally, you can remove the export directory and log files by adding the appropriate flags. For more
options, check `sparv clean -h`.

## Information Commands

All of the following commands except `sparv language` should be run from inside a corpus directory. The output of these
commands will differ depending on the corpus language configured in the corpus configuration file.

### `sparv modules`

The `sparv modules` command lists all available modules and annotations for the language specified in the corpus
configuration file. This command is useful for finding the names of annotations you want to include in your corpus
configuration, and available options for each module.

### `sparv presets`

This command lists all annotation presets available for the current language. For more details, see the [Annotation
Presets section](corpus-configuration.md#annotation-presets).

### `sparv classes`

This command lists all available annotation classes for the current language. For more information, refer to the
[Annotation Classes section](corpus-configuration.md#annotation-classes).

### `sparv languages`

This command lists all languages supported by Sparv. It can be run from any directory.

## Inspecting Corpus Details

### `sparv config`

Displays the complete configuration for your corpus, including all default values. More information can be found in the
[corpus configuration section](corpus-configuration.md).

### `sparv files`

This command displays a list of all source files available in your corpus. The files are shown without their extensions,
which is also the format used when referencing specific files for annotation with the `--file` argument in the `run`
command.

## Setting Up Sparv

### `sparv setup` and `sparv build-models`

These commands are used to set up the Sparv data directory and download and build the Sparv models, respectively. They
are detailed in the [Setting Up Sparv section](installation-and-setup.md#setting-up-sparv).

## Advanced Commands

### `sparv run-rule` and `sparv create-file`

These commands allow you to run specific annotation processors or create specific files. They are mostly useful for
debugging and testing. You can provide multiple arguments to these commands.

Example of running the Stanza annotations (part-of-speech tagging and dependency parsing) for all input files:

```sh
sparv run-rule stanza:annotate
```

Example of creating the part-of-speech annotation for the input file `document1`:

```sh
sparv create-file sparv-workdir/document1/segment.token/stanza.pos
```

### `sparv preload`

This command preloads annotators, their models, and related binaries to speed up the annotation process. This is
particularly useful when working with multiple smaller source files, as it prevents the need to load models repeatedly
for each file. Note that not all annotators support preloading; use the `--list` argument to see which annotators are
supported.

The Sparv preloader can be run from any directory containing a `config.yaml` file. While this file follows the same
format as corpus configuration files, it doesn't need to be tied to a specific corpus. The only requirement is a
`preload:` section listing the annotators to preload (as provided by the `--list` command). These annotators will be
loaded using the settings in the configuration file, combined with default settings as needed.

The preloader can be shared across multiple corpora, provided the annotator configurations (e.g., models used) are
consistent. If Sparv detects a configuration mismatch, it will automatically revert to not using the preloader for that
annotator.

The preloader uses socket files for communication. Use the `--socket` argument to specify the path to the socket file.
If omitted, the default `sparv.socket` will be used.

The `--processes` argument specifies the number of parallel processes to start. Ideally, this should match the number of
processes you plan to use when running Sparv (e.g., `sparv run -j 4`) to avoid bottlenecks.

Example of starting the preloader with four parallel processes:

```sh
sparv preload --socket my_socket.sock --processes 4
```

Once the preloader is running, use another terminal to annotate your corpus. To make Sparv use the preloader, use the
`--socket` argument and point it to the same socket file created by the preloader. For example:

```sh
sparv run --socket my_socket.sock
```

If the preloader is busy, Sparv will default to running annotators the regular way. To force Sparv to wait for the
preloader, use the `--force-preloader` flag with the `run` command.

To shut down the preloader, either press Ctrl-C in the preloader terminal or use the following command, specifying the
relevant socket:

```sh
sparv preload stop --socket my_socket.sock
```
