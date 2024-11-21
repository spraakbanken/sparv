# Wildcards

Some processors use wildcards in their input and output, allowing them to produce various annotations with different
wildcard values. For example, the annotator `misc.number_by_position` uses wildcards. Its output is defined as
`Output("{annotation}:misc.number_position")`. Here, the wildcard `{annotation}` can be replaced with any annotation,
and the annotator will generate a new attribute for the spans of that annotation. If a user requests the annotation
`<sentence>:misc.number_position` (by including it in one of the export lists in the corpus config), Sparv will add
numbers to every sentence. Similarly, requesting `document:misc.number_position` will add a number attribute to the
`document` annotation.

Wildcards are similar to config variables as they provide customization to annotators. However, the main difference is
that a config variable is explicitly set in the corpus configuration, while a wildcard receives its value automatically
when referenced in an annotation.

Wildcards in function parameters are always enclosed in curly brackets `{}`. They must also be declared in the
`wildcards` argument of the `@annotator` decorator, as shown in the following example:

```python
@annotator("Number {annotation} by position", wildcards=[Wildcard("annotation", Wildcard.ANNOTATION)])
def number_by_position(
    out: Output = Output("{annotation}:misc.number_position"),
    chunk: Annotation = Annotation("{annotation}"),
    ...
):
    ...
```

For a wildcard to be meaningful, the same wildcard variable must be used in both the input annotation (typically
`Annotation`) and the output annotation (e.g., `Output`) within the same annotation function.

An annotator can also have multiple wildcards, as demonstrated in the following example:

```python
@annotator(
    "Number {annotation} by relative position within {parent}",
    wildcards=[Wildcard("annotation", Wildcard.ANNOTATION), Wildcard("parent", Wildcard.ANNOTATION)],
)
def number_relative(
    out: Output = Output("{annotation}:misc.number_rel_{parent}"),
    parent: Annotation = Annotation("{parent}"),
    child: Annotation = Annotation("{annotation}"),
    ...
):
    ...
```

The `Wildcard` class is described on the [Sparv Classes](sparv-classes.md) page.
