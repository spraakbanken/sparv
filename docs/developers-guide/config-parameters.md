# Config Parameters

Sparv allows users to customize its functions by setting configuration parameters in the [corpus config
file](../user-manual/corpus-configuration.md). Each [Sparv decorator](sparv-decorators.md) (excluding `@wizard`) has a
`config` parameter that accepts a list of `Config` objects. Each `Config` object represents a configuration parameter,
consisting of a name, a description, and an optional default value. These configuration parameters can then be
referenced in the signature of the decorated function (or other functions) using either the `Config` class or the
`[...]` syntax in other Sparv classes' parameters. Below is an example of how to declare and use configuration
parameters in a Sparv annotator, demonstrating both methods of referencing the configuration values in the function
signature:

```python
@annotator(
    "Word sense disambiguation",
    config=[
        Config("wsd.sense_model", default="wsd/ALL_512_128_w10_A2_140403_ctx1.bin", description="Path to sense model"),
        Config("wsd.jar", default="wsd/saldowsd.jar", description="Path name of the executable .jar file"),
        Config("wsd.default_prob", default=-1.0, description="Default value for unanalyzed senses"),
        ...
    ],
)
def annotate(
    wsdjar: Binary = Binary("[wsd.jar]"),
    sense_model: Model = Model("[wsd.sense_model]"),
    default_prob: float = Config("wsd.default_prob"),
    ...
):
    ...
```

Configuration parameters can also be declared in the module's `__init__.py` file using the global variable `__config__`:

```python
__config__ = [
    Config("korp.remote_host", description="Remote host to install to"),
    Config("korp.mysql_dbname", description="Name of database where Korp data will be stored")
]
```

Where a configuration parameter is declared does not matter; it can be in the same decorator as the function using it or
in a different decorator or even a different module. The important thing is that the configuration parameter is declared
before it is used in a function signature. Typically, the configuration parameters are declared in the same decorator as
the function using them, and for configuration parameters that are used by multiple functions, they are declared in the
module's `__init__.py` file.

The way a Sparv function accesses configuration values is always through its parameters, as shown in the example above.
The configuration file should never be read directly by a Sparv module. Instead, the configuration values are passed to
the module by the Sparv core when the module is executed. This ensures that the Sparv core handles the reading of the
corpus configuration, respecting the internal [config hierarchy](#config-hierarchy) and [config
inheritance](#config-inheritance).

It is mandatory to provide a description for each declared configuration parameter. These descriptions are displayed to
the user when listing modules with the `sparv modules` command.

## Config Validation

The `Config` class includes several parameters for validating configuration values. Beyond specifying the data type
(e.g., `int`, `float`, `str`, `bool`), you can define a list of valid values, a range of values, or a regular expression
pattern that the value must match. For a comprehensive list of available parameters, refer to the [Sparv
Classes](sparv-classes.md#config) page.

It is recommended to at least specify the data type for each configuration parameter. In future versions of Sparv, this
may become a requirement.

The validation parameters are also used to generate the Sparv configuration JSON schema, which can be used to validate
corpus configuration files outside of Sparv.

## Config Hierarchy

When Sparv processes the corpus configuration, it searches for configuration values in the following order of priority:

1. The user's corpus configuration file
2. A parent corpus configuration file
3. The default configuration file in the [Sparv data
   directory](../user-manual/installation-and-setup.md#setting-up-sparv)
4. Default values defined in Sparv decorators (as shown above)

This hierarchy means that a default value specified in a Sparv decorator can be overridden by the default configuration
file, which can, in turn, be overridden by the user's corpus configuration file.

## Config Inheritance

Sparv importers and exporters inherit their configuration from the general config categories `import` and `export`. For
example, when setting `export.annotations` as follows:

```yaml
export:
    annotations:
        - <token>:hunpos.pos
        - <token>:saldo.baseform
```

the config parameter `csv_export.annotations` for the CSV exporter will automatically be set to the same value, unless
explicitly overridden in the corpus config file:

```yaml
csv_export:
    annotations:
        - <token>:hunpos.pos
        - <token>:saldo.baseform
```

This means that when writing an importer or exporter, you should use the predefined configuration key names wherever
possible, unless there is a compelling reason not to. Below is a list of existing configuration keys for the `import`
and `export` categories that are inherited by importers and exporters:

### Inheritable Configuration Keys for `import`

| Config Key          | Description                                                                 |
|:--------------------|:----------------------------------------------------------------------------|
| `text_annotation`   | The annotation representing one text. Any text-level annotations will be attached to this annotation. |
| `encoding`          | Encoding of the source file. Defaults to UTF-8.                             |
| `keep_control_chars`| Set to True if control characters should not be removed from the text.      |
| `normalize`         | Normalize input using any of the following forms: 'NFC', 'NFKC', 'NFD', and 'NFKD'. |
| `source_dir`        | The path to the directory containing the source files relative to the corpus directory. |

### Inheritable Configuration Keys for `export`

| Config Key                | Description                                                                 |
|:--------------------------|:----------------------------------------------------------------------------|
| `default`                 | Exports to create by default when running 'sparv run'.                      |
| `source_annotations`      | List of annotations from the source file to be kept.                        |
| `annotations`             | List of automatic annotations to include.                                   |
| `word`                    | The token strings to be included in the export.                             |
| `remove_module_namespaces`| Set to false if module namespaces should be kept in the export.             |
| `sparv_namespace`         | A string representing the namespace to be added to all annotations created by Sparv. |
| `source_namespace`        | A string representing the namespace to be added to all annotations present in the source. |
| `scramble_on`             | Chunk to scramble the XML export on.                                        |
