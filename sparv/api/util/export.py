"""`sparv.api.util.export` provides utility functions for preparing data for export."""

from __future__ import annotations

import re
import xml.etree.ElementTree as etree  # noqa: N813
from array import array
from collections import OrderedDict, defaultdict
from collections.abc import Iterable, Sequence
from copy import deepcopy
from functools import partial
from graphlib import CycleError, TopologicalSorter
from heapq import heapify, heappop, heappush
from itertools import chain, combinations, groupby
from operator import attrgetter
from typing import Any, ClassVar, Literal, TypeVar, cast, overload

from sparv.api import (
    Annotation,
    AnnotationAllSourceFiles,
    AnnotationName,
    Config,
    ExportAnnotations,
    ExportAnnotationsAllSourceFiles,
    HeaderAnnotations,
    Namespaces,
    SourceAnnotations,
    SourceAnnotationsAllSourceFiles,
    SparvErrorMessage,
    get_logger,
    util,
)
from sparv.core import io, registry

from .constants import SPARV_DEFAULT_NAMESPACE, XML_NAMESPACE_SEP

logger = get_logger(__name__)

AnnotationType = TypeVar("AnnotationType", bound=Annotation | AnnotationAllSourceFiles)
_OrderNode = TypeVar("_OrderNode", str, int)
_PAIR_SIZE = 2
_DEFAULT_SPAN_ORDER = (
    ("<text>", "<paragraph>"),
    ("<paragraph>", "<sentence>"),
    ("<sentence>", "<token>"),
)


class Span:
    """Object to store span information."""

    elem_hierarchy: ClassVar[dict[str, dict[str, int]]] = {}  # Set before sorting

    __slots__ = (
        "end",
        "end_sub",
        "export",
        "index",
        "is_header",
        "name",
        "node",
        "overlap_id",
        "start",
        "start_sub",
    )

    def __init__(
        self,
        name: str,
        index: int,
        start: tuple[int, ...],
        end: tuple[int, ...],
        export_names: dict[str, str],
        is_header: bool,
    ) -> None:
        """Set attributes."""
        self.name = name
        self.index = index
        self.start = start[0]
        self.end = end[0]
        self.start_sub = start[1] if len(start) > 1 else False
        self.end_sub = end[1] if len(end) > 1 else False
        self.export = export_names.get(self.name, self.name)
        self.is_header = is_header
        self.node = None
        self.overlap_id = None

    def set_node(self, parent_node: etree.Element | None = None) -> None:
        """Create an XML node under parent_node.

        Args:
            parent_node: The parent node to create the XML node under. If None, create a root node.
        """
        if parent_node is not None:
            self.node = etree.SubElement(parent_node, self.export)
        else:
            self.node = etree.Element(self.export)

    def require_node(self) -> etree.Element:
        """Return the XML node for this span, asserting that it has been created."""
        assert self.node is not None
        return self.node

    def __repr__(self) -> str:
        """Stringify the most interesting span info (for debugging mostly).

        Returns:
            A string representation of the span.
        """
        if self.export != self.name:
            return f"<{self.name}/{self.export} {self.index} {self.start}-{self.end}>"
        return f"<{self.name} {self.index} {self.start}-{self.end}>"

    def __lt__(self, other_span: Span) -> bool:
        """Return True if other_span comes after this span.

        Sort spans according to their position and hierarchy. Sort by:
        1. start position (smaller indices first)
        2. end position (larger indices first)
        3. the calculated element hierarchy
        """

        def get_sort_key(span: Span, hierarchy: int, sub_positions: bool = False, empty_span: bool = False) -> tuple:
            """Return a sort key for span which makes span comparison possible."""
            if empty_span:
                if sub_positions:
                    return (span.start, span.start_sub), hierarchy, (span.end, span.end_sub)
                return span.start, hierarchy, span.end
            else:  # noqa: RET505
                if sub_positions:
                    return (span.start, span.start_sub), (-span.end, -span.end_sub), hierarchy
                return span.start, -span.end, hierarchy

        if self.name in Span.elem_hierarchy and other_span.name in Span.elem_hierarchy[self.name]:
            self_hierarchy = Span.elem_hierarchy[self.name][other_span.name]
            other_hierarchy = 0 if self_hierarchy == 1 else 1
        else:
            self_hierarchy = other_hierarchy = -1

        # Sort empty spans according to hierarchy or put them first
        if (self.start, self.start_sub) == (self.end, self.end_sub) or (other_span.start, other_span.start_sub) == (
            other_span.end,
            other_span.end_sub,
        ):
            sort_key1 = get_sort_key(self, self_hierarchy, empty_span=True)
            sort_key2 = get_sort_key(other_span, other_hierarchy, empty_span=True)
        # Both spans have sub positions
        elif self.start_sub is not False and other_span.start_sub is not False:
            sort_key1 = get_sort_key(self, self_hierarchy, sub_positions=True)
            sort_key2 = get_sort_key(other_span, other_hierarchy, sub_positions=True)
        # At least one of the spans does not have sub positions
        else:
            sort_key1 = get_sort_key(self, self_hierarchy)
            sort_key2 = get_sort_key(other_span, other_hierarchy)

        return sort_key1 < sort_key2


def _add_precedence(successors: dict[_OrderNode, set[_OrderNode]], outer: _OrderNode, inner: _OrderNode) -> None:
    """Update the transitive order with the relation if it would keep the order acyclic."""
    if outer == inner or outer in successors.get(inner, ()):
        return
    descendants = {inner, *successors.get(inner, ())}
    successors.setdefault(outer, set()).update(descendants)
    for earlier in successors.values():
        if outer in earlier:
            earlier.update(descendants)


class SpanOrder:
    """Relative order of annotation types for spans with identical character boundaries."""

    def __init__(
        self,
        rules: Iterable[tuple[str, str]],
        defaults: Iterable[tuple[str, str]] = (),
        *,
        output_rules: Iterable[tuple[str, str]] = (),
    ) -> None:
        """Combine explicit outer/inner rules and compatible defaults.

        Args:
            rules: Declared pairs of annotation names, ordered outermost first.
            defaults: Pairs to apply where compatible with the declarations.
            output_rules: Annotator-declared pairs, between corpus rules and built-in defaults in priority.

        Raises:
            SparvErrorMessage: If the declared rules contain a cycle.
        """
        declared: dict[str, set[str]] = {}
        sorter: TopologicalSorter[str] = TopologicalSorter()
        for outer, inner in rules:
            sorter.add(inner, outer)
            _add_precedence(declared, outer, inner)
        try:
            sorter.prepare()
        except CycleError as error:
            cycle = " → ".join(error.args[1])
            raise SparvErrorMessage(f"Conflicting span order rules form a cycle: {cycle}") from None

        # Keep the priority at which each pair becomes reachable, including through intermediate annotations.
        self._priority: dict[tuple[str, str], int] = {}
        for priority, additional_rules in enumerate(((), output_rules, defaults), start=1):
            for outer, inner in additional_rules:
                _add_precedence(declared, outer, inner)
            for outer, children in declared.items():
                for inner in children:
                    self._priority.setdefault((outer, inner), priority)

    def __repr__(self) -> str:
        """Return a string representation of the span order."""
        return f"{type(self).__name__}({sorted(self._priority.items())!r})"

    def _order_group(self, spans: list[Span], hierarchy: dict[str, dict[str, int]]) -> list[Span]:
        """Order a group using source subpositions, declarations, defaults and inference.

        Returns:
            The spans in opening order.
        """
        spans.sort(key=attrgetter("name", "index"))
        preferences: list[tuple[int, int, int]] = []
        for i, j in combinations(range(len(spans)), 2):
            a, b = spans[i], spans[j]
            # If both spans have sub positions, use them to determine the order.
            if a.start_sub is not False and b.start_sub is not False:
                a_sub = (a.start_sub, -a.end_sub)
                b_sub = (b.start_sub, -b.end_sub)
                if a_sub != b_sub:
                    preferences.append((0, i, j) if a_sub < b_sub else (0, j, i))
                    continue

            if (priority := self._priority.get((a.name, b.name))) is not None:
                preferences.append((priority, i, j))
            elif (priority := self._priority.get((b.name, a.name))) is not None:
                preferences.append((priority, j, i))
            elif (inferred := hierarchy.get(a.name, {}).get(b.name)) is not None:
                preferences.append((4, i, j) if inferred == 0 else (4, j, i))

        if len(spans) == _PAIR_SIZE:
            return spans[::-1] if preferences and preferences[0][1] == 1 else spans
        if not preferences:
            return spans

        successors: dict[int, set[int]] = {}
        for _, outer, inner in sorted(preferences):
            _add_precedence(successors, outer, inner)

        # The TopologicalSorter determines a valid order of the spans based on the precedence relations.
        sorter: TopologicalSorter[int] = TopologicalSorter()
        for outer in range(len(spans)):
            sorter.add(outer)
            for inner in successors.get(outer, ()):
                sorter.add(inner, outer)
        sorter.prepare()
        ready = list(sorter.get_ready())
        # Use a heap to always pop the smallest index from the ready set (for efficiency).
        heapify(ready)
        ordered: list[Span] = []
        while ready:
            # Pop the smallest index from the ready set and add it to the ordered list.
            index = heappop(ready)
            ordered.append(spans[index])
            # Mark the index as done and add any new ready indices to the heap.
            sorter.done(index)
            for next_index in sorter.get_ready():
                heappush(ready, next_index)
        return ordered

    def apply(self, spans: list[Span], hierarchy: dict[str, dict[str, int]]) -> None:
        """Reorder non-empty spans with identical start and end positions in a list of spans sorted by position.

        Args:
            spans: Spans sorted by position, updated in place.
            hierarchy: Inferred preferences between annotation types.
        """
        for _, group in groupby(enumerate(spans), key=lambda entry: entry[1].start):
            first = next(group)
            second = next(group, None)  # ruff: ignore[reuse-of-groupby-generator]
            if second is None:
                continue
            by_end: dict[int, list[int]] = defaultdict(list)
            for i, span in chain((first, second), group):
                if span.start != span.end:
                    by_end[span.end].append(i)
            for indices in by_end.values():
                if len(indices) > 1:
                    ordered = self._order_group([spans[i] for i in indices], hierarchy)
                    for i, span in zip(indices, ordered, strict=True):
                        spans[i] = span


def _resolve_span_order(value: list[list[str]], config_name: str) -> SpanOrder:
    """Validate span rules and resolve annotation classes during rule construction.

    Returns:
        Ordering rules using the resolved annotation names.

    Raises:
        SparvErrorMessage: If the config contains an invalid or unresolved rule.
    """

    def resolve(pair: Sequence[str], source: str) -> tuple[str, str] | None:
        outer, inner = (AnnotationName(name) for name in pair)
        missing = outer.expand_variables() + inner.expand_variables()
        if missing:
            return None
        if outer.has_attribute() or inner.has_attribute():
            raise SparvErrorMessage(f"{source} requires span annotations without attributes.")
        return outer.name, inner.name

    if not isinstance(value, list):
        raise SparvErrorMessage(f"{config_name} must be a list of annotation pairs.")
    rules = []
    for pair in value:
        match pair:
            case [str(outer), str(inner)] if outer.strip() and inner.strip():
                if (order := resolve((outer.strip(), inner.strip()), config_name)) is None:
                    raise SparvErrorMessage(f"Unresolved annotation reference in {config_name}: {pair!r}")
                rules.append(order)
            case _:
                raise SparvErrorMessage(f"Each entry in {config_name} must be a list of two annotation names.")
    output_rules = [
        order
        for pair in sorted(set(registry.iter_output_span_order()))
        if (order := resolve(pair, f"Output span order {pair!r}")) is not None
    ]
    defaults = [order for pair in _DEFAULT_SPAN_ORDER if (order := resolve(pair, config_name)) is not None]
    return SpanOrder(rules, defaults, output_rules=output_rules)


def span_order_config(name: str, default: list[list[str]] | None = None) -> Config:
    """Define span order settings with the same validation and built-in rules across exporters.

    Args:
        name: Full config key.
        default: Default list of pairs, or `None` to let the exporter inherit the shared setting.

    Returns:
        Config declaration that resolves to a `SpanOrder` when used as an exporter parameter.
    """
    return Config(
        name,
        default=default,
        description="Pairs of annotation names in outer, inner order for spans with identical boundaries.",
        datatype=list[list],
        transform=partial(_resolve_span_order, config_name=name),
    )


SPAN_ORDER_CONFIG = span_order_config("export.span_order", default=[])


@overload
def gather_annotations(
    annotations: list[Annotation | AnnotationAllSourceFiles],
    export_names: dict[str, str],
    header_annotations: list[Annotation] | None = None,
    source_file: str | None = None,
    flatten: Literal[True] = True,
    split_overlaps: bool = False,
    *,
    span_order: SpanOrder | None = None,
) -> tuple[list[tuple[int, str, Span]], dict[str, dict[str, list[str]]]]: ...


@overload
def gather_annotations(
    annotations: list[Annotation | AnnotationAllSourceFiles],
    export_names: dict[str, str],
    header_annotations: list[Annotation] | None = None,
    source_file: str | None = None,
    *,
    flatten: Literal[False],
    split_overlaps: bool = False,
    span_order: SpanOrder | None = None,
) -> tuple[dict[int, list[tuple[str, Span]]], dict[str, dict[str, list[str]]]]: ...


def gather_annotations(
    annotations: list[Annotation | AnnotationAllSourceFiles],
    export_names: dict[str, str],
    header_annotations: list[Annotation] | None = None,
    source_file: str | None = None,
    flatten: bool = True,
    split_overlaps: bool = False,
    *,
    span_order: SpanOrder | None = None,
) -> (
    tuple[list[tuple[int, str, Span]], dict[str, dict[str, list[str]]]]
    | tuple[dict[int, list[tuple[str, Span]]], dict[str, dict[str, list[str]]]]
):
    """Calculate the span hierarchy and the `annotation_dict` containing all annotation elements and attributes.

    Args:
        annotations: List of annotations to include.
        export_names: Dictionary that maps from annotation names to export names.
        header_annotations: List of header annotations.
        source_file: The source filename. Omitting this is deprecated and will stop being supported in a future major
            version.
        flatten: Whether to return the spans as a flat list.
        split_overlaps: Whether to split up overlapping spans.
        span_order: Optional ordering rules for non-empty spans with identical start and end positions.

    Returns:
        If `flatten` is `True`, a list of tuples with span positions and the `annotation_dict`. If `flatten` is
            `False`, a dictionary mapping span positions to lists of spans and the `annotation_dict`.

    Raises:
        SparvErrorMessage: If the source file is not found for header annotations.
    """
    if header_annotations is None:
        header_annotations = []

    if source_file is None:
        if any(isinstance(annotation, AnnotationAllSourceFiles) for annotation in annotations):
            raise SparvErrorMessage(
                "source_file must be set when using AnnotationAllSourceFiles in gather_annotations()."
            )
        logger.warning(
            "Calling gather_annotations() without source_file is deprecated and will stop being supported in a "
            "future major release.",
        )
        inferred_source_files = {
            annotation.source_file
            for annotation in [*annotations, *header_annotations]
            if isinstance(annotation, Annotation) and annotation.source_file is not None
        }
        if len(inferred_source_files) > 1:
            raise SparvErrorMessage(
                "gather_annotations() got annotations from multiple source files while source_file was omitted."
            )
        if len(inferred_source_files) == 1:
            source_file = inferred_source_files.pop()

    resolved_annotations: list[Annotation] = []
    for annotation in annotations:
        if isinstance(annotation, AnnotationAllSourceFiles):
            if source_file is None:
                raise SparvErrorMessage(
                    "source_file must be set when using AnnotationAllSourceFiles in gather_annotations()."
                )
            resolved_annotations.append(annotation(source_file))
        else:
            resolved_annotations.append(annotation)

    # Collect annotation information and list of all annotation spans
    annotation_dict = defaultdict(dict)
    spans_list: list[Span] = []
    for annots, is_header in ((resolved_annotations, False), (header_annotations, True)):
        for annotation in sorted(annots):
            base_name, attr = annotation.split()
            if not attr:
                annotation_dict[base_name] = {}
                for i, s in enumerate(annotation.read_spans(decimals=True)):
                    spans_list.append(Span(base_name, i, s[0], s[1], export_names, is_header))
            # TODO: assemble all attrs first and use read_annotation_attributes
            if attr and not annotation_dict[base_name].get(attr):
                annotation_dict[base_name][attr] = list(annotation.read())
            elif is_header:
                try:
                    annotation_dict[base_name][util.constants.HEADER_CONTENTS] = list(
                        Annotation(f"{base_name}:{util.constants.HEADER_CONTENTS}", source_file=source_file).read()
                    )
                except FileNotFoundError:
                    raise SparvErrorMessage(
                        f"Could not find data for XML header '{base_name}'. "
                        "Was this element listed in 'xml_import.header_elements'?"
                    ) from None

    # Calculate hierarchy (if needed) and sort the span objects
    Span.elem_hierarchy = calculate_element_hierarchy(source_file, spans_list)
    sorted_spans = sorted(spans_list)
    if span_order is not None:
        span_order.apply(sorted_spans, Span.elem_hierarchy)

    # Add position information to sorted_spans
    spans_dict: defaultdict[int, list[tuple[str, Span]]] = defaultdict(list)
    for span in sorted_spans:
        # Treat empty spans differently
        if span.start == span.end:
            insert_index = len(spans_dict[span.start])
            if span.name in Span.elem_hierarchy:
                for i, (instruction, s) in enumerate(spans_dict[span.start]):
                    if (
                        instruction == "close"
                        and s.name in Span.elem_hierarchy[span.name]
                        and Span.elem_hierarchy[span.name][s.name] == 1
                    ):
                        insert_index = i
                        break
            spans_dict[span.start].insert(insert_index, ("open", span))
            spans_dict[span.end].insert(insert_index + 1, ("close", span))
        else:
            # Append opening spans; prepend closing spans
            spans_dict[span.start].append(("open", span))
            spans_dict[span.end].insert(0, ("close", span))

    # Should overlapping spans be split?
    if split_overlaps:
        _handle_overlaps(spans_dict)

    # Return the span_dict without converting to list first
    if not flatten:
        return spans_dict, annotation_dict

    # Flatten structure
    span_positions = [(pos, span[0], span[1]) for pos, spans in sorted(spans_dict.items()) for span in spans]
    return span_positions, annotation_dict


def _handle_overlaps(spans_dict: dict[int, list[tuple[str, Span]]]) -> None:
    """Handle overlapping spans by splitting them and assigning unique IDs to maintain their original relationships.

    Overlapping spans, such as <aaa> ... <b> ... </aaa> ... </b>, need to be split for certain export formats,
    like XML, which do not support overlapping tags.

    Args:
        spans_dict: A dictionary mapping span positions to the spans that open and close at those positions.
    """
    span_stack = []
    overlap_count = 0
    for position in sorted(spans_dict):
        subposition_shift = 0
        for subposition, (event, span) in enumerate(spans_dict[position].copy()):
            if event == "open":
                span_stack.append(span)
            elif event == "close":
                closing_span = span_stack.pop()
                if closing_span != span:
                    # Overlapping spans found
                    overlap_stack = []

                    # Close all overlapping spans and add an overlap ID to them
                    while closing_span != span:
                        overlap_count += 1
                        closing_span.overlap_id = overlap_count

                        # Create a copy of this span, to be reopened after we close this one
                        new_span = deepcopy(closing_span)
                        new_span.start = span.end
                        overlap_stack.append(new_span)

                        # Replace the original overlapping span with the new copy
                        end_subposition = spans_dict[closing_span.end].index(("close", closing_span))
                        spans_dict[closing_span.end][end_subposition] = ("close", new_span)

                        # Close this overlapping span
                        closing_span.end = span.end
                        spans_dict[position].insert(subposition + subposition_shift, ("close", closing_span))
                        subposition_shift += 1

                        # Fetch a new closing span from the stack
                        closing_span = span_stack.pop()

                    # Re-open overlapping spans
                    while overlap_stack:
                        overlap_span = overlap_stack.pop()
                        span_stack.append(overlap_span)
                        spans_dict[position].insert(subposition + subposition_shift + 1, ("open", overlap_span))
                        subposition_shift += 1


_SET_LOOKUP_MAX = 5_000_000  # Max number of keys to put in a temporary set when comparing two elements


def _share_any_key(span_keys: dict[str, array | list], keys_sorted: dict[str, bool], a: str, b: str) -> bool:
    """Check whether elements `a` and `b` have at least one identical (packed) span.

    If the smaller element is small enough, its keys are put in a set and the other element's keys are looked up in it
    (fast, C-level iteration). Otherwise, both key sequences are sorted and walked in parallel, which needs no extra
    memory beyond the sorting.

    Args:
        span_keys: Mapping from element name to its span keys.
        keys_sorted: Mapping from element name to whether its keys are already sorted.
        a: First element name.
        b: Second element name.

    Returns:
        True if the elements share at least one span.
    """
    small, large = sorted((a, b), key=lambda name: len(span_keys[name]))
    if len(span_keys[small]) <= _SET_LOOKUP_MAX:
        return not set(span_keys[small]).isdisjoint(span_keys[large])

    for name in (small, large):
        if not keys_sorted[name]:
            keys = span_keys[name]
            span_keys[name] = array("q", sorted(keys)) if isinstance(keys, array) else sorted(keys)
            keys_sorted[name] = True
    iter_a, iter_b = iter(span_keys[a]), iter(span_keys[b])
    try:
        key_a, key_b = next(iter_a), next(iter_b)
        while True:
            if key_a == key_b:
                return True
            if key_a < key_b:
                key_a = next(iter_a)
            else:
                key_b = next(iter_b)
    except StopIteration:
        return False


def calculate_element_hierarchy(source_file: str | None, spans_list: list[Span]) -> dict[str, dict[str, int]]:
    """Calculate the hierarchy for spans with identical start and end positions.

    If two spans A and B have identical start and end positions, go through all occurrences of A and B
    and check which element is most often parent to the other.

    Args:
        source_file: The source filename.
        spans_list: List of spans to check for hierarchy.

    Returns:
        A dictionary with the hierarchy of spans.

    Raises:
        SparvErrorMessage: If span collisions require hierarchy resolution and `source_file` is missing.
    """
    # This function used to keep a dict entry with a set for every span and every span boundary, which for large source
    # files (tens of millions of tokens) required tens of gigabytes of memory. The implementation below computes exactly
    # the same relation pairs using compact per-element arrays instead.

    # Collect the (start, end) positions of every element, packed into a single integer per span. We don't include
    # sub-positions here as we still need to compare spans with sub-positions with spans without.
    max_pos = min_pos = 0
    for span in spans_list:
        max_pos = max(max_pos, span.start, span.end)
        min_pos = min(min_pos, span.start, span.end)
    base = max_pos + 1
    # Packed keys must be unique and fit in a signed 64-bit integer; otherwise fall back to (start, end) tuples
    use_packed = min_pos >= 0 and base * base < 2**63
    span_keys: dict[str, array | list] = {}
    keys_sorted: dict[str, bool] = {}
    empty_span_starts = defaultdict(set)
    for span in spans_list:
        key = span.start * base + span.end if use_packed else (span.start, span.end)
        keys = span_keys.get(span.name)
        if keys is None:
            keys = span_keys[span.name] = array("q") if use_packed else []
            keys_sorted[span.name] = True
        elif keys_sorted[span.name] and key < keys[-1]:
            keys_sorted[span.name] = False
        keys.append(key)
        if (span.start, span.start_sub) == (span.end, span.end_sub):
            empty_span_starts[span.name].add(span.start)

    # Find pairs of elements with identical spans
    relation_pairs = set()
    for a, b in combinations(sorted(span_keys), r=2):
        if _share_any_key(span_keys, keys_sorted, a, b):
            relation_pairs.add((a, b))

    # Add empty spans and spans with identical start positions. Only the positions where empty spans start are relevant,
    # so we only keep track of non-empty spans starting or ending at those positions.
    if empty_span_starts:
        empty_positions = set().union(*empty_span_starts.values())
        startend_positions = defaultdict(set)
        for span in spans_list:
            if (span.start, span.start_sub) != (span.end, span.end_sub):
                if span.start in empty_positions:
                    startend_positions[span.start].add(span.name)
                if span.end in empty_positions:
                    startend_positions[span.end].add(span.name)
        for empty_span, span_starts in empty_span_starts.items():
            for span_start in span_starts:
                relation_pairs.update(tuple(sorted((empty_span, a))) for a in startend_positions.get(span_start, ()))

    hierarchy = defaultdict(dict)

    if relation_pairs and source_file is None:
        raise SparvErrorMessage(
            "source_file must be set to resolve element hierarchy for annotations with colliding spans."
        )

    # Calculate parent-child relation for every pair
    for a, b in relation_pairs:
        a_annot = Annotation(a, source_file=source_file)
        b_annot = Annotation(b, source_file=source_file)
        a_parent = sum(1 for i in b_annot.get_parents(a_annot) if i is not None)
        b_parent = sum(1 for i in a_annot.get_parents(b_annot) if i is not None)
        if a_parent > b_parent:
            hierarchy[a][b] = 0
            hierarchy[b][a] = 1
        elif a_parent < b_parent:
            hierarchy[b][a] = 0
            hierarchy[a][b] = 1

    return hierarchy


def get_annotation_names(
    annotations: ExportAnnotations | ExportAnnotationsAllSourceFiles | Sequence[tuple[AnnotationType, str | None]],
    source_annotations: (
        SourceAnnotations | SourceAnnotationsAllSourceFiles | Sequence[tuple[AnnotationType, str | None]] | None
    ) = None,
    source_file: str | None = None,
    token_name: str | None = None,
    remove_namespaces: bool = False,
    keep_struct_names: bool = False,
    sparv_namespace: str | None = None,
    source_namespace: str | None = None,
    xml_mode: bool = False,
) -> tuple[list[AnnotationType], list[str], dict[str, str]]:
    """Get a list of annotations, token attributes, and a dictionary translating annotation names to export names.

    Args:
        annotations: List of elements:attributes (annotations) to include, with possible export names.
        source_annotations: List of elements:attributes from the source file to include, with possible export names. If
            not specified, includes everything.
        source_file: Name of the source file.
        token_name: Name of the token annotation.
        remove_namespaces: Set to `True` to remove all namespaces in `export_names` unless names are ambiguous.
        keep_struct_names: Set to `True` to include the annotation base name (everything before ":") in `export_names`
            for annotations that are not token attributes.
        sparv_namespace: Namespace to add to all Sparv annotations.
        source_namespace: Namespace to add to all annotations from the source file.
        xml_mode: Set to `True` to use XML namespaces in `export_names`.

    Returns:
        A list of annotations, a list of token attribute names, a dictionary with translation from annotation names to
            export names.
    """
    annotation_items = cast(list[tuple[AnnotationType, str | None]], list(annotations))
    source_annotation_items = cast(list[tuple[AnnotationType, str | None]], list(source_annotations or []))

    # Combine all annotations
    all_annotations = _remove_duplicates(annotation_items + source_annotation_items)

    if token_name:
        # Get the names of all token attributes
        token_attributes = [
            a[0].attribute_name for a in all_annotations if a[0].annotation_name == token_name and a[0].attribute_name
        ]
    else:
        token_attributes = []

    # Get XML namespaces
    xml_namespaces = Namespaces(source_file).read() if source_file else {}

    export_names = _create_export_names(
        all_annotations,
        token_name,
        remove_namespaces,
        keep_struct_names,
        source_annotation_items,
        sparv_namespace,
        source_namespace,
        xml_namespaces,
        xml_mode=xml_mode,
    )

    return [cast(AnnotationType, i[0]) for i in all_annotations], token_attributes, export_names


def get_header_names(
    header_annotations: HeaderAnnotations,
    xml_namespaces: dict[str, str],
) -> tuple[list[Annotation], dict[str, str]]:
    """Get a list of header annotations and a dictionary for renamed annotations.

    Args:
        header_annotations: List of header annotations from the source file to include. If not specified,
            includes everything.
        xml_namespaces: XML namespaces to use for the header annotations.

    Returns:
        A list of header annotations and a dictionary with translation from annotation names to export names.
    """
    export_names = _create_export_names(
        list(header_annotations), None, False, keep_struct_names=False, xml_namespaces=xml_namespaces, xml_mode=True
    )

    return [a[0] for a in header_annotations], export_names


def _remove_duplicates(
    annotation_tuples: Sequence[tuple[AnnotationType, str | None]],
) -> list[tuple[AnnotationType, str | None]]:
    """Remove duplicates from annotation_tuples without changing the order.

    Args:
        annotation_tuples: Sequence of tuples containing annotations and their export names.

    Returns:
        A list of tuples with unique annotations and their export names.
    """
    new_annotations = OrderedDict()
    seen_names = set()
    for a, new_name in annotation_tuples:
        if a.name not in seen_names or new_name is not None:
            new_annotations[a] = new_name
            seen_names.add(a.name)
    return list(new_annotations.items())


def _create_export_names(
    annotations: Sequence[tuple[Annotation | AnnotationAllSourceFiles, str | None]],
    token_name: str | None,
    remove_namespaces: bool,
    keep_struct_names: bool,
    source_annotations: Iterable[tuple[Annotation | AnnotationAllSourceFiles, str | None]] = (),
    sparv_namespace: str | None = None,
    source_namespace: str | None = None,
    xml_namespaces: dict | None = None,
    xml_mode: bool = False,
) -> dict[str, str]:
    """Create dictionary with translation from annotation names to export names.

    Args:
        annotations: List of tuples containing annotations and their export names.
        token_name: Name of the token annotation. Required if `remove_namespaces` or `keep_struct_names` is `True`.
        remove_namespaces: Set to `True` to remove all namespaces from the export names unless names are ambiguous.
        keep_struct_names: Set to `True` to include the annotation base name (everything before ":") in the export names
            for annotations that are not token attributes.
        source_annotations: List of source annotations.
        sparv_namespace: Namespace to add to all Sparv annotations.
        source_namespace: Namespace to add to all annotations from the source file.
        xml_namespaces: Dictionary of XML namespaces.
        xml_mode: Set to `True` to use XML namespaces in the export names.

    Returns:
        A dictionary with translation from annotation names to export names.

    Raises:
        ValueError: If `token_name` is missing when `keep_struct_names` is `True`.
    """
    if xml_namespaces is None:
        xml_namespaces = {}
    if keep_struct_names:
        if token_name is None:
            raise ValueError("token_name must be set if keep_struct_names is True")
        token_name_str = token_name
    else:
        token_name_str = ""

    if remove_namespaces:

        def shorten(annotation: Annotation | AnnotationAllSourceFiles) -> str:
            """Shorten annotation name or attribute name.

            For example:
                segment.token -> token
                segment.token:saldo.baseform -> segment.token:baseform

            Args:
                annotation: The annotation to shorten.

            Returns:
                The shortened annotation name.
            """

            def remove_before_dot(name: str) -> str:
                # Always remove "custom."
                name = name.removeprefix("custom.")
                # Remove everything before first "."
                if "." in name:
                    name = name.split(".", 1)[1]
                return name

            if annotation.attribute_name:
                short = io.join_annotation(annotation.annotation_name, remove_before_dot(annotation.attribute_name))
            else:
                short = io.join_annotation(remove_before_dot(annotation.annotation_name), None)
            return short

        # Create short names dictionary and count
        short_names_count = defaultdict(int)
        short_names = {}
        for annotation, new_name in annotations:
            name = annotation.name
            if new_name:
                # If attribute, combine new attribute name with base annotation name
                short_name = io.join_annotation(annotation.annotation_name, new_name) if ":" in name else new_name
            else:
                # Don't remove namespaces from elements and attributes contained in the source files
                short_name = name if (annotation, new_name) in source_annotations else shorten(annotation)
            short_names_count[short_name] += 1
            base, attr = Annotation(short_name).split()
            short_names[name] = attr or base

        export_names = {}
        for annotation, new_name in sorted(annotations):  # Sorted in order to handle annotations before attributes
            name = annotation.name
            if not new_name:
                # Only use short name if it's unique
                if "." in name and short_names_count[shorten(annotation)] == 1:
                    new_name = short_names[name]  # noqa: PLW2901
                else:
                    new_name = annotation.attribute_name or annotation.annotation_name  # noqa: PLW2901

            # Keep annotation base name (the part before ":") if this is not a token attribute
            if keep_struct_names and ":" in name and not name.startswith(token_name_str):
                base_name = annotation.annotation_name
                new_name = io.join_annotation(export_names.get(base_name, base_name), new_name)  # noqa: PLW2901
            export_names[name] = new_name
    else:  # noqa: PLR5501
        if keep_struct_names:
            export_names = {}
            for annotation, new_name in sorted(annotations):  # Sorted in order to handle annotations before attributes
                name = annotation.name
                if not new_name:
                    new_name = annotation.attribute_name or annotation.annotation_name  # noqa: PLW2901
                if ":" in name and not name.startswith(token_name_str):
                    base_name = annotation.annotation_name
                    new_name = io.join_annotation(export_names.get(base_name, base_name), new_name)  # noqa: PLW2901
                export_names[name] = new_name
        else:
            export_names = {
                annotation.name: (new_name or annotation.attribute_name or annotation.name)
                for annotation, new_name in annotations
            }

    export_names = _add_global_namespaces(
        export_names, annotations, source_annotations, sparv_namespace, source_namespace
    )
    export_names = _check_name_collision(export_names, source_annotations)

    # Take care of XML namespaces
    export_names = {k: _get_xml_tagname(v, xml_namespaces, xml_mode) for k, v in export_names.items()}

    return export_names  # noqa: RET504


def _get_xml_tagname(tag: str, xml_namespaces: dict, xml_mode: bool = False) -> str:
    """Take care of namespaces by looking up URIs for prefixes (if xml_mode=True) or by converting to dot notation.

    Args:
        tag: The tag name to convert.
        xml_namespaces: A dictionary of XML namespaces.
        xml_mode: If `True`, convert prefixes to URIs.

    Returns:
        The converted tag name.

    Raises:
        SparvErrorMessage: If the namespace prefix is not found in `xml_namespaces`.
    """
    sep = re.escape(XML_NAMESPACE_SEP)
    m = re.match(rf"(.*){sep}(.+)", tag)
    if m:
        if xml_mode:
            # Replace prefix+tag with {uri}tag
            uri = xml_namespaces.get(m.group(1), "")
            if not uri:
                raise SparvErrorMessage(
                    f"You are trying to export the annotation '{tag}' but no URI was found for the "
                    f"namespace prefix '{m.group(1)}'!"
                )
            return re.sub(rf"(.*){sep}(.+)", rf"{{{uri}}}\2", tag)
        elif m.group(1):  # noqa: RET505
            # Replace "prefix+tag" with "prefix.tag", skip this for default namespaces
            return re.sub(rf"(.*){sep}(.+)", r"\1.\2", tag)
    return tag


def _add_global_namespaces(
    export_names: dict,
    annotations: Sequence[tuple[Annotation | AnnotationAllSourceFiles, Any]],
    source_annotations: Iterable,
    sparv_namespace: str | None = None,
    source_namespace: str | None = None,
) -> dict:
    """Add sparv_namespace and source_namespace to export names.

    Args:
        export_names: Dictionary with export names.
        annotations: List of all Sparv annotations for the corpus.
        source_annotations: List of source annotations.
        sparv_namespace: Namespace to add to all Sparv annotations.
        source_namespace: Namespace to add to all annotations from the source file.

    Returns:
        A dictionary with updated export names.
    """
    source_annotation_names = [a.name for a, _ in source_annotations]

    if sparv_namespace:
        for a, _ in annotations:
            name = a.name
            if name not in source_annotation_names:
                export_names[name] = f"{sparv_namespace}.{export_names.get(name, name)}"

    if source_namespace:
        for name in source_annotation_names:
            export_names[name] = f"{source_namespace}.{export_names.get(name, name)}"

    return export_names


def _check_name_collision(export_names: dict, source_annotations: Iterable) -> dict:
    """Detect collisions in attribute names and resolve them or send warnings.

    Args:
        export_names: Dictionary with export names.
        source_annotations: List of source annotations.

    Returns:
        A dictionary with updated export names.
    """
    source_names = [a.name for a, _ in source_annotations]

    # Get annotations with identical export attribute names
    reverse_index = defaultdict(set)
    for k, v in export_names.items():
        if ":" in k:
            reverse_index[v].add(k)
    possible_collisions = {k: [Annotation(v) for v in values] for k, values in reverse_index.items() if len(values) > 1}
    # Only keep the ones with matching element names
    for attr, values in possible_collisions.items():
        attr_dict = defaultdict(list)
        for v in values:
            attr_dict[v.annotation_name].append(v)
        attr_collisions = {k: v for k, v in attr_dict.items() if len(v) > 1}
        for annots in attr_collisions.values():
            # If there are two colliding attributes and one is an automatic one, prefix it with SPARV_DEFAULT_NAMESPACE
            if len(annots) == 2 and len([a for a in annots if a.name not in source_names]) == 1:  # noqa: PLR2004
                sparv_annot = annots[0] if annots[0].name not in source_names else annots[1]
                source_annot = annots[0] if annots[0].name in source_names else annots[1]
                new_name = SPARV_DEFAULT_NAMESPACE + "." + export_names[sparv_annot.name]
                export_names[sparv_annot.name] = new_name
                logger.info(
                    "Changing name of automatic annotation '%s' to '%s' due to collision with '%s'.",
                    sparv_annot.name,
                    new_name,
                    source_annot.name,
                )
            # Warn the user if we cannot resolve collisions automatically
            else:
                annots_string = "\n".join(
                    [f"{a.name} ({'source' if a.name in source_names else 'sparv'} annotation)" for a in annots]
                )
                logger.warning(
                    "The following annotations are exported with the same name (%s) and might overwrite "
                    "each other: \n\n%s\n\nIf you want to keep all of these annotations you can change "
                    "their export names.",
                    attr,
                    annots_string,
                )
    return export_names


################################################################################
# Scrambling
################################################################################


def scramble_spans(span_positions: list[tuple], chunk_name: str, chunk_order: Sequence[str | int]) -> list[tuple]:
    """Reorder spans based on `chunk_order` and ensure tags are opened and closed correctly.

    Args:
        span_positions: Original span positions, typically obtained from `gather_annotations()`.
        chunk_name: Name of the annotation to reorder.
        chunk_order: Sequence of numbers (as strings or integers) specifying the new order of the chunks. The numbers
            should correspond to the indices of the chunks in the original order.

    Returns:
        List of tuples with the new span positions and instructions.
    """
    new_s_order = _reorder_spans(span_positions, chunk_name, chunk_order)
    _fix_parents(new_s_order, chunk_name)

    # Reformat span positions
    new_span_positions = [v for k, v in sorted(new_s_order.items())]  # Sort dict into list
    new_span_positions = [t for s in new_span_positions for t in s]  # Unpack chunks
    new_span_positions = [(0, instruction, span) for instruction, span in new_span_positions]  # Add fake position (0)

    return new_span_positions  # noqa: RET504


def _reorder_spans(span_positions: list[tuple], chunk_name: str, chunk_order: Sequence[str | int]) -> dict:
    """Scramble chunks according to the chunk_order.

    Args:
        span_positions: Original span positions, typically obtained from `gather_annotations()`.
        chunk_name: Name of the annotation to reorder.
        chunk_order: Sequence of numbers (as strings or integers) specifying the new order of the chunks. The numbers
            should correspond to the indices of the chunks in the original order.

    Returns:
        Dictionary with the new span positions and instructions.
    """
    new_s_order = defaultdict(list)
    parent_stack = []
    temp_stack = []
    current_s_index = None
    last_s_index = None

    for _pos, instruction, span in span_positions:
        if instruction == "open":
            if span.name == chunk_name and current_s_index is None:  # Check current_s_index to avoid nested chunks
                current_s_index = int(chunk_order[span.index])

                for temp_instruction, temp_span in temp_stack:
                    if current_s_index == last_s_index:
                        # Continuing split annotation
                        new_s_order[current_s_index].append((temp_instruction, temp_span))

                    if temp_instruction == "open":
                        parent_stack.append((temp_instruction, temp_span))
                    elif temp_instruction == "close" and parent_stack[-1][1] == temp_span:
                        parent_stack.pop()

                temp_stack = []

                # If this is the start of this chunk, add all open parents first
                if not new_s_order[current_s_index]:
                    new_s_order[current_s_index].extend(parent_stack)
                new_s_order[current_s_index].append((instruction, span))
            elif current_s_index is not None:
                # Encountered child to chunk
                new_s_order[current_s_index].append((instruction, span))
            else:
                # Encountered parent to chunk
                temp_stack.append((instruction, span))

        elif instruction == "close":
            if current_s_index is not None:
                # Encountered child to chunk
                new_s_order[current_s_index].append((instruction, span))
                # If chunk, check index to make sure it's the right chunk and not a nested one
                if span.name == chunk_name and int(chunk_order[span.index]) == current_s_index:
                    last_s_index = current_s_index
                    current_s_index = None
            else:
                # Encountered parent to chunk
                temp_stack.append((instruction, span))

    return new_s_order


def _fix_parents(new_s_order: dict, chunk_name: str) -> None:
    """Go through new_s_order, remove duplicate opened parents and close parents.

    Args:
        new_s_order: Dictionary with the new span positions and instructions.
        chunk_name: Name of the annotation used to reorder the chunks.
    """
    open_parents = []
    new_s_order_indices = sorted(new_s_order.keys())
    for i, s_index in enumerate(new_s_order_indices):
        chunk = new_s_order[s_index]
        is_parent = True
        current_chunk_index = None
        for instruction, span in chunk:
            if instruction == "open":
                if span.name == chunk_name and current_chunk_index is None:
                    is_parent = False
                    current_chunk_index = span.index
                elif is_parent:
                    open_parents.append((instruction, span))
            else:  # "close"  # noqa: PLR5501
                # If chunk, check index to make sure it's the right chunk and not a nested one
                if span.name == chunk_name and span.index == current_chunk_index:
                    is_parent = True
                    current_chunk_index = None
                elif is_parent:
                    if open_parents[-1][1] == span:
                        open_parents.pop()
        # Check next chunk: close parents in current chunk that are not part of next chunk and
        # remove already opened parents from next chunk
        if i < len(new_s_order_indices) - 1:  # noqa: SIM108
            next_chunk = new_s_order[new_s_order_indices[i + 1]]
        else:
            next_chunk = []
        for p in reversed(open_parents):
            if p in next_chunk:
                next_chunk.remove(p)
            else:
                chunk.append(("close", p[1]))
                open_parents.remove(p)
