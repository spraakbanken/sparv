# General Concepts

This section provides a brief overview of how Sparv modules work and introduces some general concepts. More details are
provided in the following chapters.

Sparv consists of a core and various modules. These modules contain Sparv functions that serve different
purposes, such as reading and parsing source files, building or downloading models, producing annotations, and
generating output files that contain the source text and annotations. All of these modules (i.e., the code inside the
`sparv/modules` directory) are replaceable. A Sparv function is decorated with a special
[decorator](sparv-decorators.md) that indicates its purpose. A function's parameters specify the input needed to run the
function and the output it produces. The Sparv core automatically discovers all decorated functions, scans their
parameters, and builds a registry of available modules and their dependencies.

## Annotations

The most common Sparv function is the [annotator](sparv-decorators.md#annotator), which produces one or more
annotations. An annotation consists of spans that indicate the text positions it covers and an optional attribute for
each span. For example, a function that segments a text into tokens produces a span annotation that specifies where each
token begins and ends in the source text. A function that produces part-of-speech tags, on the other hand, relies on the
token spans produced by another function and adds an attribute for each token span, indicating whether the token is a
noun, verb, or another part of speech.

Annotations are referred to by their internal names, which follow a strict naming convention. The name of a span
annotation starts with the name of the module that produces it, followed by a dot, and an arbitrary name consisting of
lowercase ASCII letters, numbers, and underscores. For example, the token span annotation produced by the `segment`
module is called `segment.token`. The name of an attribute annotation follows the same rules, except that it is prefixed
with the name of the span annotation it adds attributes to, followed by a colon. So the part-of-speech annotation
produced by the `stanza` module is called `segment.token:stanza.pos` because it adds part-of-speech attributes to the
`segment.token` span annotation.

## Dependencies

Some Sparv functions may require annotations from other functions before they can be run. These dependencies are
expressed in the function arguments. By using special [Sparv classes](sparv-classes.md) as default arguments in a
function's signature, the central Sparv registry can automatically track which annotations can be produced by which
function and in what order they need to be run. These dependencies can be described in a module-specific manner or in a
more abstract way. For example, an annotator producing word base forms (or lemmas) may depend on a part-of-speech
annotation with a specific tagset and therefore might define that its input needs to be an annotation produced by a
specific module. A part-of-speech tagger, on the other hand, usually needs word segments as input, and it probably does
not matter which module produces these segments. In this case, the dependency can be expressed with an abstract
[annotation class](#annotation-classes).

## Annotation Classes

When describing dependencies on other annotations, one can use annotation classes, denoted by angle brackets (e.g.,
`<token>`, `<token:word>`). Annotation classes create abstract instances for common annotations such as tokens,
sentences, and text units. They simplify dependencies between annotation modules and increase the flexibility of the
annotation pipeline. Many annotation modules need tokenized text as input, but they might not care which tokenizer is
used. So instead of specifying that a module needs tokens produced by another specific module, we can tell it to take
the class `<token>` as input. In the [corpus configuration](../user-manual/corpus-configuration.md), we can then set
`classes.token` to `segment.token`, which tells Sparv that `<token>` refers to output produced by the `segment` module.

Annotation classes are valid across all modules and may be used wherever needed. There is no closed set of annotation
classes, and each module can invent its own classes if desired. Within a corpus directory, all existing classes can be
listed with the `sparv classes` command.
