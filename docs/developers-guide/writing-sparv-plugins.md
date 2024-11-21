# Writing Sparv Plugins

The Sparv Pipeline consists of various processors such as importers, annotators, and exporters, contained in so-called
modules. While many modules come with the main Sparv package, none are mandatory to use, and you can easily extend the
pipeline with your own modules using plugins. A plugin is simply a Sparv module that is not part of the main package.
Writing a plugin is the recommended way to add a new module to Sparv.

> [!NOTE]
> When writing a plugin, always prefix your Python package with a namespace followed by an underscore to
> indicate the organization or developer the plugin belongs to. This avoids package name clashes and will be enforced in
> the future. In the example below, we use the prefix "sbx_" (for Språkbanken Text).

For your first plugin, we recommend looking at the [Sparv plugin
template](https://github.com/spraakbanken/sparv-plugin-template). The template includes an example of a small annotation
module that converts tokens to uppercase. We will use this template in the examples below.

## Plugin Structure

A typical plugin structure looks like this:

```text
sparv-sbx-uppercase/
├── sbx_uppercase
│   ├── uppercase.py
│   └── __init__.py
├── LICENSE
├── pyproject.toml
└── README.md
```

In this example, the `sbx_uppercase` directory is a Sparv module containing the [module code](#module-code) in
`uppercase.py` and the mandatory [init file](#init-file) `__init__.py`. The [project file](#pyprojecttoml)
`pyproject.toml` in the root directory is needed to install the plugin.

While the readme and license files are not strictly necessary for the plugin to work, we strongly recommend including
them if you plan to publish your plugin.

## pyproject.toml

The `pyproject.toml` file is required to install a plugin and connect it to the Sparv Pipeline. Here is a minimal
example (taken from the [Sparv plugin template](https://github.com/spraakbanken/sparv-plugin-template)):

```toml
[project]
name = "sparv-sbx-uppercase"
version = "0.1.0"
description = "Uppercase converter (example plug-in for Sparv)"
readme = "README.md"
license.text = "MIT License"
dependencies = [
    "sparv-pipeline~=5.0"
]
entry-points."sparv.plugin" = { sbx_uppercase = "sbx_uppercase" }
```

Ensure there is a `sparv.plugin` entry point in `project.entry-points` that points to your module (the directory
containing the code). It is also advisable to add `sparv-pipeline` to the list of dependencies, specifying the major
version of Sparv the plugin is developed for. `"sparv-pipeline~=5.0"` under `dependencies` means the plugin is
compatible with any version of Sparv 5, but not with Sparv 4 or Sparv 6.

We strongly encourage you to include the `project.authors` field.

For more information about `pyproject.toml`, check the [Python Packaging User
Guide](https://packaging.python.org/en/latest/specifications/declaring-project-metadata/).

## Init File

Each Sparv module requires an [`__init__.py`](https://docs.python.org/3/reference/import.html#regular-packages) file,
which is essential for Sparv to recognize and register the module. This file should import the Python scripts containing
your decorated Sparv functions. Additionally, any module-specific configuration parameters can be set here.

The `__init__.py` file must include a short (one sentence) description of the module. This description will appear when
running the `sparv modules` command. You can provide this description using the `__description__` variable or as a
docstring. In the example below, both methods are shown, but only one is necessary. If both are present, the
`__description__` value takes precedence.

A longer description can be included by adding additional lines, separated from the first line by a blank line. Only the
first line will be shown in space-limited contexts, such as `sparv modules`. The full description will appear when
running `sparv modules modulename`.

Example of an `__init__.py` file:

```python
"""Example of a Sparv annotator that converts tokens to uppercase."""

# from sparv.api import Config

from . import uppercase

# __config__ = [
#     Config("uppercase.some_setting", "some_default_value", description="Description for this setting")
# ]

__description__ = "Example of a Sparv annotator that converts tokens to uppercase."
```

## Module Code

A Sparv module is a Python package that includes at least one Python script utilizing [Sparv
decorators](sparv-decorators.md), [Sparv classes](sparv-classes.md) and, if necessary, [utility
functions](utilities.md). These imports help describe dependencies on other entities, such as annotations or models,
that the pipeline handles or creates. Below is the code for our uppercase example, taken from the [Sparv plugin
template](https://github.com/spraakbanken/sparv-plugin-template):

```python
from sparv.api import Annotation, Output, annotator

@annotator("Convert every word to uppercase.")
def uppercase(
    word: Annotation = Annotation("<token:word>"),
    out: Output = Output("<token>:sbx_uppercase.upper")
):
    """Convert to uppercase."""
    out.write([val.upper() for val in word.read()])
```

In this script, we import two classes from Sparv (`Annotation` and `Output`) and the `annotator` decorator. It is
important to only import from the `sparv.api` package (i.e., `from sparv.api import ...`). Other sub-packages, like
`sparv.core`, are for internal use only and may change without notice.

The `uppercase` function is decorated with `@annotator`, indicating that this function can produce one or more
annotations. The first argument in the decorator is a description used for displaying help texts in the CLI, such as
when running `sparv modules`.

The function's signature describes its relationship to other pipeline components. The parameters include type hints to
the Sparv classes `Annotation` and `Output`, with the accompanying default values specifying the dependencies (e.g.,
annotations, models, or config variables) required before the function can execute, and what it will produce. In this
example, Sparv ensures that a word annotation exists before calling the `uppercase` function, as `word` is an input of
type `Annotation`. The function produces the output annotation `<token>:sbx_uppercase.upper`, so if another module
requests this annotation as input, Sparv will run `uppercase` first.

A function decorated with a Sparv decorator should never be called directly by you or another decorated function. When
running Sparv through the CLI, Sparv's dependency system calculates a dependency graph and automatically runs all
necessary functions to produce the desired output.

## Reading and Writing Files

Sparv classes such as `Annotation` and `Output` provide built-in methods for reading and writing files, as seen with
`word.read()` and `out.write()` in the example above. It is crucial that a Sparv module uses these methods exclusively
for file operations. This practice ensures that files are correctly placed within the file structure, making them
accessible to other modules. Additionally, these methods handle Sparv's internal data format properly. Bypassing these
methods can cause procedures to fail if there are updates to the internal data format or file structure in the future.

## Logging

To log messages from Sparv modules, use [Python's logging library](https://docs.python.org/3.6/library/logging.html).
Utilize the provided `get_logger` wrapper to declare your logger, which handles importing the logging library and sets
the correct module name in the log output:

```python
from sparv.api import get_logger
logger = get_logger(__name__)
logger.error("An error was encountered!")
```

You can use any of the official [Python logging levels](https://docs.python.org/3.6/library/logging.html#levels).

By default, Sparv writes log output with level WARNING and higher to the terminal. Users can change the log level with
the `--log [LOGLEVEL]` flag, which is supported by most commands. Additionally, users can write log output to a file
using the `--log-to-file [LOGLEVEL]` flag. The log file will be named with the current date and timestamp and can be
found in the `logs/` directory within the corpus directory.

### Progress Bar

You can add a progress bar to individual annotators using the custom `progress()` logging method. Initialize the
progress bar by calling `logger.progress()`, either without arguments or by supplying a total value:
`logger.progress(total=50)`. A progress bar initialized without a total will need a total value before it can be used.
You can also change the total value later.

Once the total is set, update the progress by calling `logger.progress()` again. If no argument is supplied, the
progress advances by 1. To advance by a different amount, use the `advance=` keyword argument. To set the progress to a
specific number, call the method with that number as the argument. Here are some examples:

```python
from sparv.api import get_logger
logger = get_logger(__name__)

# Initialize progress bar with no known total
logger.progress()

# Initialize bar with known total
logger.progress(total=50)

# Advance progress by 1
logger.progress()

# Advance progress by 2
logger.progress(advance=2)

# Set progress to 5
logger.progress(5)
```

## Error Messages

To notify users of critical errors (e.g., when they have made a mistake), use the [SparvErrorMessage
class](utilities.md#sparverrormessage). This class raises an exception, halts the current Sparv process, and displays a
user-friendly error message without showing the usual Python traceback.

```python
from sparv.api import SparvErrorMessage

@annotator("Convert every word to uppercase")
def uppercase(word: Annotation = Annotation("<token:word>"),
              out: Output = Output("<token>:sbx_uppercase.upper"),
              important_config_variable: str = Config("sbx_uppercase.some_setting")):
    """Convert to uppercase."""
    # Ensure important_config_variable is set by the user
    if not important_config_variable:
        raise SparvErrorMessage("Please set the config variable 'sbx_uppercase.some_setting'!")
    ...
```

## Languages and Varieties

To restrict an annotator, exporter, installer, or model builder to specific languages, use the `language` parameter in
the decorator and provide a list of ISO 639-3 language codes:

```python
@annotator("Convert every word to uppercase", language=["swe", "eng"])
def ...
```

These Sparv functions will only be available if one of their specified languages matches the language in the [corpus
config file](../user-manual/corpus-configuration.md). If no language codes are specified, the function will be available
for any corpus.

To restrict an entire module to specific languages, assign a list of language codes to the `__language__` variable in
the module's `__init__.py` file. This will restrict all functions in the module to the specified languages.

Sparv also supports language varieties, which is useful for functions targeting specific varieties of a language. For
example, Sparv has annotators for historical Swedish from the 1800s, marked with the language code `swe-1800`. Here,
`swe` is the ISO 639-3 code for Swedish, and `1800` is an arbitrary string representing the variety. Functions marked
with `swe-1800` will be available for corpora configured as follows:

```yaml
metadata:
    language: "swe"
    variety: "1800"
```

Functions marked with `swe` will also be available for these corpora.

## Installing and Uninstalling Plugins

Installation and uninstallation of Sparv plugins are handled by the `sparv plugins` command. How to use this command is
described in the [Installation and Setup](../user-manual/installation-and-setup.md#installing-and-uninstalling-plugins)
section of the user manual.

> [!TIP]
> To make development easier, you can install a plugin in **editable mode**. This means that changes to the plugin code
> will immediately be available to Sparv without having to reinstall the plugin. This is done by using the `-e` flag
> when installing from a local directory:
>
> ```sh
> sparv plugins install -e ./sparv-sbx-uppercase
> ```

## Advanced Features

This section covers advanced features that can enhance your plugins but are not essential for basic plugin development.

### Function Order

In some cases, you may need to create multiple Sparv functions that generate the same output files (such as annotation
files, export files, or model files). Sparv needs to know the priority of these functions to determine which one to use.
For example, consider two functions, `annotate()` and `annotate_backoff()`, both producing an annotation output called
`mymodule.foo`. Ideally, `mymodule.foo` should be produced by `annotate()`. However, if `annotate()` cannot run (perhaps
because it requires another annotation file `mymodule.bar` that is unavailable for some corpora), you want
`annotate_backoff()` to produce `mymodule.foo` instead.

The priority of functions is specified using the `order` argument in the `@annotator`, `@exporter`, or `@modelbuilder`
decorator. A lower number indicates a higher priority.

```python
@annotator("Create foo annotation", order=1)
def annotate(
    out: Output = Output("mymodule.foo"),
    bar_input: Annotation = Annotation("mymodule.bar")):
    ...


@annotator("Create foo annotation when bar is not available", order=2)
def annotate_backoff(
    out: Output = Output("mymodule.foo")):
    ...
```

<!-- Functions with a higher order number can explicitly be called with `sparv run-rule`. Not working at the moment due to a bug! -->

### Preloaders

Preloader functions are used by the `sparv preload` command to speed up the annotation process. They work by preloading
the Python module along with models or processes that would otherwise need to be loaded for each source file.

A preloader function takes a subset of the arguments from an annotator and returns a value that is passed to the
annotator. Here is an example:

```python
from sparv.api import Annotation, Model, Output, annotator

def preloader(model):
    """Preload POS model."""
    return load_model(model)

@annotator("Part-of-speech tagging.",
           preloader=preloader,
           preloader_params=["model"],
           preloader_target="model_preloaded")
def pos_tag(word: Annotation = Annotation("<token:word>"),
            out: Output = Output("<token>:pos.tag"),
            model: Model = Model("pos.model"),
            model_preloaded=None):
    """Annotate tokens with POS tags."""
    if model_preloaded:
        model = model_preloaded
    else:
        model = load_model(model)
```

In this example, the annotator uses a model and has an extra argument called `model_preloaded`, which can optionally
take an already loaded model. The `preloader` parameter in the decorator points to the preloader function. The
`preloader_params` list specifies the annotator parameters needed by the preloader, in this case, just the `model`
parameter. The `preloader_target` points to the annotator parameter that will receive the preloaded value.

When using the `sparv preload` command with this annotator, the preloader function runs once, and every time the
annotator is used, it receives the preloaded model via the `model_preloaded` parameter.

The `preloader`, `preloader_params`, and `preloader_target` parameters are required when adding a preloader to an
annotator. There are also two optional parameters: `preloader_shared` and `preloader_cleanup`.

`preloader_shared` is a boolean that defaults to True. By default, Sparv runs the preloader function once, and if using
`sparv preload` with multiple parallel processes, they all share the preloaded result. Setting `preloader_shared` to
False makes the preloader function run once per process, which is usually needed when preloading processes rather than
models.

`preloader_cleanup` refers to a function that runs after each (preloaded) use of the annotator. This function should
take the same arguments as the preloader function, plus an extra argument for the preloaded value. It should return the
same type of object as the preloader function, which Sparv will use as the new preloaded value. This is rarely needed
but can be useful for preloading processes that need regular restarting. The cleanup function would track when
restarting is needed, call the preloader function to start a new process, and return it.
