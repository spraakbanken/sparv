"""Small annotators that don't fit as standalone python files."""

import re
from typing import List, Optional

from sparv import Annotation, Output, Text, annotator, util


@annotator("Text value of a span (usually a token)")
def text_spans(text: Text = Text(),
               chunk: Annotation = Annotation("<token>"),
               out: Output = Output("<token>:misc.word", cls="token:word")):
    """Add the text content for each edge as a new annotation."""
    corpus_text = text.read()
    if isinstance(chunk, (str, Annotation)):
        chunk = chunk.read_spans()
    out_annotation = []
    for span in chunk:
        out_annotation.append(corpus_text[span[0]:span[1]])
    if out:
        out.write(out_annotation)
    else:
        return out_annotation


@annotator("Head and tail whitespace characters for tokens")
def text_headtail(text: Text = Text(),
                  chunk: Annotation = Annotation("<token>"),
                  out_head: Output = Output("<token>:misc.head"),
                  out_tail: Output = Output("<token>:misc.tail")):
    """Extract "head" and "tail" whitespace characters for tokens."""
    def escape(t):
        """Escape whitespace characters."""
        return t.replace(" ", "\\s").replace("\n", "\\n").replace("\t", "\\t")

    out_head_annotation = chunk.create_empty_attribute()
    out_tail_annotation = chunk.create_empty_attribute()
    head_text = None

    corpus_text = text.read()
    chunk = list(chunk.read())

    for i, span in enumerate(chunk):
        if head_text:
            out_head_annotation[i] = escape(head_text)
            head_text = None

        if i < len(chunk) - 1:
            tail_start = span[1][0]
            tail_end = chunk[i + 1][0][0]
            tail_text = corpus_text[tail_start:tail_end]

            try:
                n_pos = tail_text.rindex("\n")
            except ValueError:
                n_pos = None
            if n_pos is not None and n_pos + 1 < len(tail_text):
                head_text = tail_text[n_pos + 1:]
                tail_text = tail_text[:n_pos + 1]

            if tail_text:
                out_tail_annotation[i] = escape(tail_text)

    out_head.write(out_head_annotation)
    out_tail.write(out_tail_annotation)


@annotator("Convert part-of-speech tags, specified by the mapping")
def translate_tag(out: Output,
                  tag: Annotation,
                  mapping: dict = {}):
    """Convert part-of-speech tags, specified by the mapping.

    Example mappings: parole_to_suc, suc_to_simple, ...
    """
    if isinstance(mapping, str):
        mapping = util.tagsets.__dict__[mapping]
    out.write((mapping.get(t, t) for t in tag.read()))


@annotator("Convert {struct}:{attr} into a token annotation")
def struct_to_token(attr: Annotation = Annotation("{struct}:{attr}"),
                    token: Annotation = Annotation("<token>"),
                    out: Output = Output("<token>:misc.from_struct_{struct}_{attr}")):
    """Convert an attribute on a structural annotation into a token attribute."""
    token_parents = token.get_parents(attr)
    attr_values = list(attr.read())
    out_values = [attr_values[p] if p is not None else "" for p in token_parents]
    out.write(out_values)


# TODO: Do we still need this? struct_to_token probably mostly replaces it
def chain(out, annotations, default=None):
    """Create a functional composition of a list of annotations.

    E.g., token.sentence + sentence.id -> token.sentence-id
    """
    if isinstance(annotations, str):
        annotations = annotations.split()
    annotations = [a.read() for a in annotations]
    out.write(util.corpus.chain(annotations, default))


@annotator("Create new annotation, with spans as values")
def span_as_value(chunk: Annotation,
                  out: Output):
    """Create new annotation, with spans as values."""
    out.write((f"{start}-{end}" for start, end in chunk.read_spans()))


@annotator("Select a specific index from the values of an annotation")
def select(out: Output,
           annotation: Annotation,
           index: Optional[int] = 0,
           separator: Optional[str] = " "):
    """Select a specific index from the values of an annotation.

    The given annotation values are separated by 'separator',
    by default whitespace, with at least index + 1 elements.
    """
    if isinstance(index, str):
        index = int(index)
    out.write(value.split(separator)[index] for value in annotation.read())


@annotator("Create an annotation with a constant value")
def constant(chunk: Annotation,
             out: Output,
             value: str = ""):
    """Create an annotation with a constant value."""
    out.write((value for _ in chunk.read()))


@annotator("Add prefix and/or suffix to an annotation")
def affix(chunk: Annotation,
          out: Output,
          prefix: Optional[str] = "",
          suffix: Optional[str] = ""):
    """Add prefix and/or suffix to annotation."""
    out.write([(prefix + val + suffix) for val in chunk.read()])


@annotator("Find and replace whole annotation")
def replace(chunk: Annotation,
            out: Output,
            find: str = "",
            sub: Optional[str] = ""):
    """Find and replace whole annotation. Find string must match whole annotation."""
    out.write((sub if val == find else val for val in chunk.read()))


@annotator("Find and replace whole annotation values")
def replace_list(chunk: Annotation,
                 out: Output,
                 find: str = "",
                 sub: str = ""):
    """Find and replace annotations.

    Find string must match whole annotation.
    find and sub are whitespace separated lists of words to replace and their replacement.
    """
    find = find.split()
    sub = sub.split()
    if len(find) != len(sub):
        raise util.SparvErrorMessage("Find and sub must have the same number of words.")
    translate = dict((f, s) for (f, s) in zip(find, sub))
    out.write((translate.get(val, val) for val in chunk.read()))


@annotator("Find and replace parts of or whole annotation")
def find_replace(chunk: Annotation,
                 out: Output,
                 find: str = "",
                 sub: str = ""):
    """Find and replace parts of or whole annotation."""
    out.write((val.replace(find, sub) for val in chunk.read()))


@annotator("Do find and replace in values of annotation using a regular expressions")
def find_replace_regex(chunk: Annotation,
                       out: Output,
                       find: str = "",
                       sub: str = ""):
    """Do find and replace in values of annotation using a regular expressions.

    N.B: When writing regular expressions in YAML they should be enclosed in single quotes.
    """
    out.write((re.sub(find, sub, val) for val in chunk.read()))


@annotator("Concatenate values from two annotations, with an optional separator")
def concat(out: Output,
           left: Annotation,
           right: Annotation,
           separator: str = "",
           merge_twins: bool = False):
    """Concatenate values from two annotations, with an optional separator.

    If merge_twins is set to True, no concatenation will be done on identical values.
    """
    b = list(right.read())
    out.write((f"{val_a}{separator}{b[n]}" if not (merge_twins and val_a == b[n]) else val_a
               for (n, val_a) in enumerate(left.read())))


# TODO: not working yet because we cannot handle lists of annotations as input
# @annotator("Concatenate two or more annotations, with an optional separator")
def concat2(out: Output,
            annotations: List[Annotation] = [Annotation],
            separator: str = ""):
    """Concatenate two or more annotations, with an optional separator."""
    annotations = [list(a.read()) for a in annotations]
    out.write([separator.join([a[n] for a in annotations]) for (n, _) in enumerate(annotations[0])])


@annotator("Replace empty values in 'chunk' with values from 'backoff'")
def backoff(chunk: Annotation,
            backoff: Annotation,
            out: Output):
    """Replace empty values in 'chunk' with values from 'backoff'."""
    # Function was called 'merge' before.
    backoff = list(backoff.read())
    out.write((val if val else backoff[n] for (n, val) in enumerate(chunk.read())))


@annotator("Replace values in 'chunk' with non empty values from 'repl'")
def override(chunk: Annotation,
             repl: Annotation,
             out: Output):
    """Replace values in 'chunk' with non empty values from 'repl'."""
    def empty(val):
        if not val:
            return True
        return val == "|"

    repl = list(repl.read())
    out.write((
        repl[n] if not empty(repl[n]) else val for (n, val) in enumerate(chunk.read())))


@annotator("Round floats to the given number of decimals")
def roundfloat(chunk: Annotation,
               out: Output,
               decimals: int = 2):
    """Round floats to the given number of decimals."""
    decimals = int(decimals)
    strformat = "%." + str(decimals) + "f"
    out.write((strformat % round(float(val), decimals) for val in chunk.read()))
