"""Classes used as default input for annotator functions."""

from __future__ import annotations

import gzip
import os
import pathlib
import pickle
import time
import urllib.request
import zipfile
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator, Sequence
from typing import Any, Callable

import sparv.core
from sparv.core import io
from sparv.core.misc import get_logger, parse_annotation_list
from sparv.core.paths import paths

logger = get_logger(__name__)


class Base(ABC):
    """Base class for most Sparv classes."""

    @abstractmethod
    def __init__(self, name: str = "") -> None:
        """Initialize class.

        Args:
            name: Name of the annotation/model/etc.
        """
        assert isinstance(name, str), "'name' must be a string"
        self.name = name
        self.original_name = name
        self.root = pathlib.Path.cwd()  # Save current working dir as root

    def expand_variables(self, rule_name: str = "") -> list[str]:
        """Update name by replacing <class> references with annotation names and [config] references with config values.

        Args:
            rule_name: The name of the rule using the string, for logging config usage.

        Returns:
            A list of any unresolved config references.
        """
        new_value, rest = sparv.core.registry.expand_variables(self.name, rule_name)
        self.name = new_value
        return rest

    def __contains__(self, string: str) -> bool:
        """Check if a string is contained in the name.

        Args:
            string: The string to check for.

        Returns:
            True if the string is contained in the name.
        """
        return string in self.name

    def __str__(self) -> str:
        """Return string representation of the class."""
        return self.__repr__()

    def __repr__(self) -> str:
        """Return string representation of the class."""
        return f"<{self.__class__.__name__} {self.name!r}>"

    def __format__(self, format_spec: str) -> str:
        """Return formatted string representation of the class."""
        return self.name.__format__(format_spec)

    def __lt__(self, other: Base) -> bool:
        """Compare two Base instances by name.

        Args:
            other: Another Base instance to compare with.

        Returns:
            True if self is less than other.
        """
        return self.name < other.name

    def __len__(self) -> int:
        """Return length of name."""
        return len(self.name)


class BaseAnnotation(Base):
    """An annotation or attribute used as input."""

    data = False
    all_files = False
    common = False
    is_input = True

    def __init__(self, name: str = "", source_file: str | None = None, is_input: bool | None = None) -> None:
        """Initialize class.

        Args:
            name: Name of the annotation.
            source_file: Source file for the annotation.
            is_input: Deprecated, use AnnotationName instead of setting this to False.
        """
        super().__init__(name)
        self.source_file = source_file
        if is_input is not None:
            self.is_input = is_input

    def expand_variables(self, rule_name: str = "") -> list[str]:
        """Update name by replacing <class> references with annotation names and [config] references with config values.

        Args:
            rule_name: The name of the rule using the string, for logging config usage.

        Returns:
            A list of any unresolved config references.
        """
        new_value, rest = sparv.core.registry.expand_variables(self.name, rule_name, is_annotation=True)
        self.name = new_value
        return rest

    def split(self) -> tuple[str, str]:
        """Split name into annotation name and attribute.

        Returns:
            A tuple with the annotation name and attribute name.
        """
        return io.split_annotation(self.name)

    def has_attribute(self) -> bool:
        """Return True if the annotation has an attribute."""
        return io.ELEM_ATTR_DELIM in self.name

    @property
    def annotation_name(self) -> str:
        """Get annotation name (excluding name of any attribute).

        Returns:
            The annotation name without any attribute.
        """
        return self.split()[0]

    @property
    def attribute_name(self) -> str | None:
        """Get attribute name (excluding name of annotation).

        Returns:
            The attribute name without name of annotation.
        """
        return self.split()[1] or None

    def __eq__(self, other: BaseAnnotation) -> bool:
        """Check if two BaseAnnotation instances are equal.

        Args:
            other: Another BaseAnnotation instance to compare with.

        Returns:
            True if the instances are equal.
        """
        return type(self) is type(other) and self.name == other.name and self.source_file == other.source_file

    def __hash__(self) -> int:
        """Return hash of the class instance."""
        return hash(repr(self) + repr(self.source_file))


class CommonMixin(BaseAnnotation):
    """Common methods used by many classes."""

    def exists(self) -> bool:
        """Return True if annotation file exists."""
        return io.annotation_exists(self)

    def remove(self) -> None:
        """Remove annotation file."""
        io.remove_annotation(self)


class CommonAllSourceFilesMixin(BaseAnnotation):
    """Common methods used by many classes."""

    def exists(self, source_file: str) -> bool:
        """Return True if annotation file exists."""
        return io.annotation_exists(self, source_file)

    def remove(self, source_file: str) -> None:
        """Remove annotation file."""
        io.remove_annotation(self, source_file)


class CommonAnnotationMixin(BaseAnnotation):
    """Methods common to Annotation and AnnotationAllSourceFiles."""

    def __init__(self, name: str = "", source_file: str | None = None) -> None:
        """Initialize class.

        Args:
            name: Name of the annotation.
            source_file: Source file for the annotation.
        """
        super().__init__(name, source_file)
        self._size = {}

    def _read(self, source_file: str) -> Iterator[str]:
        """Yield each line from the annotation.

        Args:
            source_file: Source file for the annotation.

        Returns:
            An iterator of lines from the annotation.
        """
        return io.read_annotation(source_file, self)

    def _read_spans(self, source_file: str, decimals: bool = False, with_annotation_name: bool = False) -> Iterator:
        """Yield the spans of the annotation.

        Args:
            source_file: Source file for the annotation.
            decimals: If True, return spans with decimals.
            with_annotation_name: If True, return spans with annotation name.

        Returns:
            An iterator of spans from the annotation.
        """
        return io.read_annotation_spans(source_file, self, decimals=decimals, with_annotation_name=with_annotation_name)

    @staticmethod
    def _read_attributes(source_file: str, annotations: list[BaseAnnotation] | tuple[BaseAnnotation, ...],
                         with_annotation_name: bool = False) -> Iterator:
        """Yield tuples of multiple attributes on the same annotation.

        Args:
            source_file: Source file for the annotation.
            annotations: List of annotations to read attributes from.
            with_annotation_name: If True, return attributes with annotation name.

        Returns:
            An iterator of tuples of attributes.
        """
        return io.read_annotation_attributes(source_file, annotations, with_annotation_name=with_annotation_name)

    def _get_size(self, source_file: str) -> int:
        """Get number of values.

        Args:
            source_file: Source file for the annotation.

        Returns:
            The number of values in the annotation.
        """
        if self._size.get(source_file) is None:
            self._size[source_file] = io.get_annotation_size(source_file, self)
        return self._size[source_file]

    def _create_empty_attribute(self, source_file: str) -> list:
        """Return a list filled with None of the same size as this annotation.

        Args:
            source_file: Source file for the annotation.

        Returns:
            A list filled with None of the same size as this annotation.
        """
        return [None] * self._get_size(source_file)

    @staticmethod
    def _read_parents_and_children(
        source_file: str,
        parent: BaseAnnotation,
        child: BaseAnnotation
    ) -> tuple[Iterator, Iterator]:
        """Read parent and child annotations.

        Args:
            source_file: Source file for the annotation.
            parent: Parent annotation.
            child: Child annotation.

        Returns:
            A tuple of iterators for parent and child annotations.
        """
        parent_spans = list(io.read_annotation_spans(source_file, parent, decimals=True))
        child_spans = list(io.read_annotation_spans(source_file, child, decimals=True))

        # Only use sub-positions if both parent and child have them
        if parent_spans and child_spans and (len(parent_spans[0][0]) == 1 or len(child_spans[0][0]) == 1):
            parent_spans = [(p[0][0], p[1][0]) for p in parent_spans]
            child_spans = [(c[0][0], c[1][0]) for c in child_spans]

        return iter(parent_spans), iter(child_spans)

    def _get_children(self, source_file: str, child: BaseAnnotation, orphan_alert: bool = False) -> tuple[list, list]:
        """Get children of this annotation.

        Args:
            source_file: Source file for the annotation.
            child: Child annotation.
            orphan_alert: If True, log a warning when a child has no parent.

        Returns:
            A tuple of two lists.
            The first one is a list with n (= total number of parents) elements where every element is a list
            of indices in the child annotation.
            The second one is a list of orphans, i.e. containing indices in the child annotation that have no parent.
            Both parents and children are sorted according to their position in the source file.
        """
        parent_spans, child_spans = self._read_parents_and_children(source_file, self, child)
        parent_children = []
        orphans = []
        previous_parent_span = None
        try:
            parent_span = next(parent_spans)
            parent_children.append([])
        except StopIteration:
            parent_span = None

        for child_i, child_span in enumerate(child_spans):
            if parent_span:
                while child_span[1] > parent_span[1]:
                    previous_parent_span = parent_span
                    try:
                        parent_span = next(parent_spans)
                        parent_children.append([])
                    except StopIteration:
                        parent_span = None
                        break
            if parent_span is None or parent_span[0] > child_span[0]:
                if orphan_alert:
                    logger.warning("Child '%s' missing parent; closest parent is %s",
                                   child_i, parent_span or previous_parent_span)
                orphans.append(child_i)
            else:
                parent_children[-1].append(child_i)

        # Add rest of parents
        if parent_span is not None:
            parent_children.extend([] for _ in parent_spans)

        return parent_children, orphans

    def _get_parents(self, source_file: str, parent: BaseAnnotation, orphan_alert: bool = False) -> list:
        """Get parents of this annotation.

        Args:
            source_file: Source file for the annotation.
            parent: Parent annotation.
            orphan_alert: If True, log a warning when a child has no parent.

        Returns:
            A list with n (= total number of children) elements where every element is an index in the parent
            annotation, or None when no parent is found.
        """
        parent_spans, child_spans = self._read_parents_and_children(source_file, parent, self)
        parent_index_spans = enumerate(parent_spans)
        child_parents = []
        previous_parent_span = None
        try:
            parent_i, parent_span = next(parent_index_spans)
        except StopIteration:
            parent_i = None
            parent_span = None

        for child_span in child_spans:
            while parent_span is not None and child_span[1] > parent_span[1]:
                previous_parent_span = parent_span
                try:
                    parent_i, parent_span = next(parent_index_spans)
                except StopIteration:
                    parent_span = None
                    break
            if parent_span is None or parent_span[0] > child_span[0]:
                if orphan_alert:
                    logger.warning("Child '%s' missing parent; closest parent is %s",
                                   child_span, parent_span or previous_parent_span)
                child_parents.append(None)
            else:
                child_parents.append(parent_i)

        return child_parents


class Annotation(CommonAnnotationMixin, CommonMixin, BaseAnnotation):
    """Regular Annotation tied to one source file."""

    def read(self) -> Iterator[str]:
        """Get an iterator of values from the annotation.

        Returns:
            An iterator of values from the annotation.
        """
        return self._read(self.source_file)

    def read_spans(self, decimals: bool = False, with_annotation_name: bool = False) -> Iterator:
        """Get an iterator of spans from the annotation.

        Args:
            decimals: If True, return spans with decimals.
            with_annotation_name: If True, return spans with annotation name.

        Returns:
            An iterator of spans from the annotation.
        """
        return self._read_spans(self.source_file, decimals=decimals, with_annotation_name=with_annotation_name)

    def read_attributes(self, annotations: list[BaseAnnotation] | tuple[BaseAnnotation, ...],
                        with_annotation_name: bool = False) -> Iterator:
        """Return an iterator of tuples of multiple attributes on the same annotation.

        Args:
            annotations: List of annotations to read attributes from.
            with_annotation_name: If True, return attributes with annotation name.

        Returns:
            An iterator of tuples of attributes.
        """
        return self._read_attributes(self.source_file, annotations, with_annotation_name)

    def get_children(self, child: BaseAnnotation, orphan_alert: bool = False) -> tuple[list, list]:
        """Get children of this annotation.

        Args:
            child: Child annotation.
            orphan_alert: If True, log a warning when a child has no parent.

        Returns:
            A tuple of two lists.

            The first one is a list with n (= total number of parents) elements where every element is a list
            of indices in the child annotation.
            The second one is a list of orphans, i.e. containing indices in the child annotation that have no parent.
            Both parents and children are sorted according to their position in the source file.
        """
        return self._get_children(self.source_file, child, orphan_alert)

    def get_parents(self, parent: BaseAnnotation, orphan_alert: bool = False) -> list:
        """Get parents of this annotation.

        Args:
            parent: Parent annotation.
            orphan_alert: If True, log a warning when a child has no parent.

        Returns:
            A list with n (= total number of children) elements where every element is an index in the parent
            annotation, or None when no parent is found.
        """
        return self._get_parents(self.source_file, parent, orphan_alert)

    def read_parents_and_children(self, parent: BaseAnnotation, child: BaseAnnotation) -> tuple[Iterator, Iterator]:
        """Read parent and child annotations.

        Reorder them according to span position, but keep original index information.

        Args:
            parent: Parent annotation.
            child: Child annotation.

        Returns:
            A tuple of iterators for parent and child annotations.
        """
        return self._read_parents_and_children(self.source_file, parent, child)

    def create_empty_attribute(self) -> list:
        """Return a list filled with None of the same size as this annotation."""
        return self._create_empty_attribute(self.source_file)

    def get_size(self) -> int:
        """Get number of values.

        Returns:
            The number of values in the annotation.
        """
        return self._get_size(self.source_file)


class AnnotationName(BaseAnnotation):
    """Class representing an Annotation name.

    To be used when only the name is of interest and not the actual annotation file.
    """

    is_input = False


class AnnotationData(CommonMixin, BaseAnnotation):
    """Annotation of the data type, not tied to spans in the corpus text."""

    data = True

    def __init__(self, name: str = "", source_file: str | None = None) -> None:
        """Initialize class.

        Args:
            name: Name of the annotation.
            source_file: Source file for the annotation.
        """
        super().__init__(name, source_file=source_file)

    def read(self, source_file: str | None = None) -> Iterator[str]:
        """Read arbitrary string data from annotation file.

        Args:
            source_file: Source file for the annotation.

        Returns:
            The data of the annotation.
        """
        return io.read_data(self.source_file or source_file, self)


class AnnotationAllSourceFiles(CommonAnnotationMixin, CommonAllSourceFilesMixin, BaseAnnotation):
    """Regular annotation but source file must be specified for all actions.

    Use as input to an annotator to require the specificed annotation for every source file in the corpus.
    """

    all_files = True

    def __init__(self, name: str = "") -> None:
        """Initialize class.

        Args:
            name: Name of the annotation.
        """
        super().__init__(name)
        self._size = {}

    def read(self, source_file: str) -> Iterator[str]:
        """Get an iterator of values from the annotation.

        Args:
            source_file: Source file for the annotation.

        Returns:
            An iterator of values from the annotation.
        """
        return self._read(source_file)

    def read_spans(self, source_file: str, decimals: bool = False, with_annotation_name: bool = False) -> Iterator:
        """Get an iterator of spans from the annotation.

        Args:
            source_file: Source file for the annotation.
            decimals: If True, return spans with decimals.
            with_annotation_name: If True, return spans with annotation name.

        Returns:
            An iterator of spans from the annotation.
        """
        return self._read_spans(source_file, decimals=decimals, with_annotation_name=with_annotation_name)

    def read_attributes(self, source_file: str, annotations: list[BaseAnnotation] | tuple[BaseAnnotation, ...],
                        with_annotation_name: bool = False) -> Iterator:
        """Return an iterator of tuples of multiple attributes on the same annotation.

        Args:
            source_file: Source file for the annotation.
            annotations: List of annotations to read attributes from.
            with_annotation_name: If True, return attributes with annotation name.

        Returns:
            An iterator of tuples of attributes.
        """
        return self._read_attributes(source_file, annotations, with_annotation_name=with_annotation_name)

    def get_children(self, source_file: str, child: BaseAnnotation, orphan_alert: bool = False) -> tuple[list, list]:
        """Get children of this annotation.

        Args:
            source_file: Source file for the annotation.
            child: Child annotation.
            orphan_alert: If True, log a warning when a child has no parent.

        Returns:
            A tuple of two lists.
            The first one is a list with n (= total number of parents) elements where every element is a list
            of indices in the child annotation.
            The second one is a list of orphans, i.e. containing indices in the child annotation that have no parent.
            Both parents and children are sorted according to their position in the source file.
        """
        return self._get_children(source_file, child, orphan_alert)

    def get_parents(self, source_file: str, parent: BaseAnnotation, orphan_alert: bool = False) -> list:
        """Get parents of this annotation.

        Args:
            source_file: Source file for the annotation.
            parent: Parent annotation.
            orphan_alert: If True, log a warning when a child has no parent.

        Returns:
            A list with n (= total number of children) elements where every element is an index in the parent
            annotation, or None when no parent is found.
        """
        return self._get_parents(source_file, parent, orphan_alert)

    def create_empty_attribute(self, source_file: str) -> list:
        """Return a list filled with None of the same size as this annotation.

        Args:
            source_file: Source file for the annotation.
        """
        return self._create_empty_attribute(source_file)

    def get_size(self, source_file: str) -> int:
        """Get number of values.

        Args:
            source_file: Source file for the annotation.

        Returns:
            The number of values in the annotation.
        """
        return self._get_size(source_file)


class AnnotationDataAllSourceFiles(CommonAllSourceFilesMixin, BaseAnnotation):
    """Data annotation but source file must be specified for all actions."""

    all_files = True
    data = True

    def __init__(self, name: str = "") -> None:
        """Initialize class.

        Args:
            name: Name of the annotation.
        """
        super().__init__(name)

    def read(self, source_file: str) -> Iterator[str]:
        """Read arbitrary string data from annotation file.

        Args:
            source_file: Source file for the annotation.

        Returns:
            The data of the annotation.
        """
        return io.read_data(source_file, self)


class AnnotationCommonData(CommonMixin, BaseAnnotation):
    """Data annotation for the whole corpus."""

    common = True
    data = True

    def __init__(self, name: str = "") -> None:
        """Initialize class.

        Args:
            name: Name of the annotation.
        """
        super().__init__(name)

    def read(self) -> Iterator[str]:
        """Read arbitrary corpus level string data from annotation file.

        Returns:
            The data of the annotation.
        """
        return io.read_data(None, self)


class Marker(AnnotationCommonData):
    """A marker indicating that something has run."""


class MarkerOptional(Marker):
    """Same as regular Marker, except if it doesn't exist, it won't be created."""

    is_input = False


class BaseOutput(BaseAnnotation):
    """Base class for all Output classes."""

    data = False
    all_files = False
    common = False

    def __init__(self, name: str = "", cls: str | None = None, description: str | None = None,
                 source_file: str | None = None) -> None:
        """Initialize class.

        Args:
            name: Name of the annotation.
            cls: Class of the annotation.
            description: Description of the annotation.
            source_file: Source file for the annotation.
        """
        super().__init__(name, source_file)
        self.cls = cls
        self.description = description


class Output(CommonMixin, BaseOutput):
    """Regular annotation or attribute used as output."""

    def __init__(self, name: str = "", cls: str | None = None, description: str | None = None,
                 source_file: str | None = None) -> None:
        """Initialize class.

        Args:
            name: Name of the annotation.
            cls: Class of the annotation.
            description: Description of the annotation.
            source_file: Source file for the annotation.
        """
        super().__init__(name, cls, description=description, source_file=source_file)

    def write(self, values: list, source_file: str | None = None) -> None:
        """Write an annotation to file. Existing annotation will be overwritten.

        Args:
            values: A list of values.
            source_file: Source file for the annotation.
        """
        io.write_annotation(self.source_file or source_file, self, values)


class OutputAllSourceFiles(CommonAllSourceFilesMixin, BaseOutput):
    """Regular annotation or attribute used as output, but source file must be specified for all actions."""

    all_files = True

    def __init__(self, name: str = "", cls: str | None = None, description: str | None = None) -> None:
        """Initialize class.

        Args:
            name: Name of the annotation.
            cls: Class of the annotation.
            description: Description of the annotation.
        """
        super().__init__(name, cls, description=description)

    def write(self, values: list, source_file: str) -> None:
        """Write an annotation to file. Existing annotation will be overwritten.

        Args:
            values: A list of values.
            source_file: Source file for the annotation.
        """
        io.write_annotation(source_file, self, values)


class OutputData(CommonMixin, BaseOutput):
    """Data annotation used as output."""

    data = True

    def __init__(self, name: str = "", cls: str | None = None, description: str | None = None,
                 source_file: str | None = None) -> None:
        """Initialize class.

        Args:
            name: Name of the annotation.
            cls: Class of the annotation.
            description: Description of the annotation.
            source_file: Source file for the annotation.
        """
        super().__init__(name, cls, description=description, source_file=source_file)

    def write(self, value: Any) -> None:
        """Write arbitrary data to annotation file.

        Args:
            value: The data to write.
        """
        io.write_data(self.source_file, self, value)


class OutputDataAllSourceFiles(CommonAllSourceFilesMixin, BaseOutput):
    """Data annotation used as output, but source file must be specified for all actions."""

    all_files = True
    data = True

    def __init__(self, name: str = "", cls: str | None = None, description: str | None = None) -> None:
        """Initialize class.

        Args:
            name: Name of the annotation.
            cls: Class of the annotation.
            description: Description of the annotation.
        """
        super().__init__(name, cls, description=description)

    def read(self, source_file: str) -> Any:
        """Read arbitrary string data from annotation file.

        Args:
            source_file: Source file for the annotation.

        Returns:
            The data of the annotation.
        """
        return io.read_data(source_file, self)

    def write(self, value: Any, source_file: str) -> None:
        """Write arbitrary data to annotation file.

        Args:
            value: The data to write.
            source_file: Source file for the annotation.
        """
        io.write_data(source_file, self, value)


class OutputCommonData(CommonMixin, BaseOutput):
    """Data annotation for the whole corpus."""

    common = True
    data = True

    def __init__(self, name: str = "", cls: str | None = None, description: str | None = None) -> None:
        """Initialize class.

        Args:
            name: Name of the annotation.
            cls: Class of the annotation.
            description: Description of the annotation.
        """
        super().__init__(name, cls, description=description)

    def write(self, value: Any) -> None:
        """Write arbitrary corpus level data to annotation file.

        Args:
            value: The data to write.
        """
        io.write_data(None, self, value)


class OutputMarker(OutputCommonData):
    """A class for creating a marker, indicating that something has run."""

    def write(self, value: str = "") -> None:
        """Create a marker, indicating that something has run.

        This is used by functions that don't have any natural output, like installers and uninstallers.

        Args:
            value: The data to write. Usually this should be left out.
        """
        # Write current timestamp, as Snakemake also compares checksums for small files, not just modified time
        super().write(value or str(time.time()))


class Text:
    """Corpus text."""

    def __init__(self, source_file: str | None = None) -> None:
        """Initialize class.

        Args:
            source_file: Source file for the annotation.
        """
        self.source_file = source_file

    def read(self) -> str:
        """Get corpus text.

        Returns:
            The corpus text.
        """
        return io.read_data(self.source_file, io.TEXT_FILE)

    def write(self, text: str) -> None:
        """Write text to the designated file of a corpus.

        Args:
            text: The text to write.
        """
        io.write_data(self.source_file, io.TEXT_FILE, text)

    def __repr__(self) -> str:
        """Return class name as string representation of the class."""
        return "<Text>"


class SourceStructure(BaseAnnotation):
    """Every annotation available in a source file."""

    data = True

    def __init__(self, source_file: str) -> None:
        """Initialize class.

        Args:
            source_file: Source file for the annotation.
        """
        super().__init__(io.STRUCTURE_FILE, source_file)

    def read(self) -> list[str]:
        """Read structure file to get a list of nams of annotations in the source file.

        Returns:
            A list of annotation names.
        """
        return io.read_data(self.source_file, self).split("\n")

    def write(self, structure: list[str]) -> None:
        """Sort the source file's structural elements and write structure file.

        Args:
            structure: A list of annotation names.
        """
        structure.sort()
        io.write_data(self.source_file, self, "\n".join(structure))


class Headers(CommonMixin, BaseAnnotation):
    """List of header annotation names."""

    data = True

    def __init__(self, source_file: str) -> None:
        """Initialize class.

        Args:
            source_file: Source file for the annotation.
        """
        super().__init__(io.HEADERS_FILE, source_file)

    def read(self) -> list[str]:
        """Read headers file.

        Returns:
            A list of header annotation names.
        """
        return io.read_data(self.source_file, self).splitlines()

    def write(self, header_annotations: list[str]) -> None:
        """Write headers file.

        Args:
            header_annotations: A list of header annotation names.
        """
        io.write_data(self.source_file, self, "\n".join(header_annotations))


class Namespaces(BaseAnnotation):
    """Namespace mapping (URI to prefix) for a source file."""

    data = True

    def __init__(self, source_file: str) -> None:
        """Initialize class.

        Args:
            source_file: Source file for the annotation.
        """
        super().__init__(io.NAMESPACE_FILE, source_file)

    def read(self) -> dict[str, str]:
        """Read namespace file and parse it into a dict.

        Returns:
            A dict with prefixes as keys and URIs as values.
        """
        try:
            lines = io.read_data(self.source_file, self).split("\n")
            return dict(l.split(" ") for l in lines)
        except FileNotFoundError:
            return {}

    def write(self, namespaces: dict[str, str]) -> None:
        """Write namespace file.

        Args:
            namespaces: A dict with prefixes as keys and URIs as values.
        """
        io.write_data(self.source_file, self, "\n".join([f"{k} {v}" for k, v in namespaces.items()]))


class SourceFilename(str):
    """Name of a source file."""


class Corpus(str):
    """Name of the corpus."""


class AllSourceFilenames(Sequence[str]):
    """List with names of all source files."""

    def __init__(self) -> None:
        """Initialize class."""
        self.items: Sequence[str] = []

    def __getitem__(self, index: int) -> str:
        """Return item at index."""
        return self.items[index]

    def __len__(self) -> int:
        """Return number of source files."""
        return len(self.items)


class Config(str):
    """Class holding configuration key names."""

    def __new__(cls, name: str, *args, **kwargs) -> str:
        return super().__new__(cls, name)

    def __init__(
        self,
        name: str,
        default: Any = None,
        description: str | None = None,
        datatype: type | None = None,
        choices: Iterable | Callable | None = None,
        pattern: str | None = None,
        min_len: int | None = None,
        max_len: int | None = None,
        min_value: int | float | None = None,
        max_value: int | float | None = None,
        const: Any | None = None,
        conditions: list[Config] | None = None
    ) -> None:
        """Initialize class.

        Args:
            name: Name of the config key.
            default: Default value of the config key.
            description: Description of the config key.
            datatype: Datatype of the config key.
            choices: A list of allowed values for the config key, or a function that returns them.
            pattern: A regex pattern that the value must match.
            min_len: Minimum length of the value.
            max_len: Maximum length of the value.
            min_value: Minimum value of the value.
            max_value: Maximum value of the value.
            const: A constant value that the value must equal.
            conditions: A list of other Config objects that must be met for this Config to be valid.
        """
        self.name = name
        self.default = default
        self.description = description
        self.datatype = datatype
        self.choices = choices
        self.pattern = pattern
        self.min_len = min_len
        self.max_len = max_len
        self.min_value = min_value
        self.max_value = max_value
        self.const = const
        self.conditions = conditions or []


class Wildcard(str):
    """Class holding wildcard information."""

    ANNOTATION = 1
    ATTRIBUTE = 2
    ANNOTATION_ATTRIBUTE = 3
    OTHER = 0

    def __new__(cls, name: str, *args, **kwargs):
        return super().__new__(cls, name)

    def __init__(self, name: str, type: int = OTHER, description: str | None = None) -> None:
        """Initialize class.

        Args:
            name: Name of the wildcard.
            type: Type of the wildcard, by reference to the constants defined in this class
                (ANNOTATION, ATTRIBUTE, ANNOTATION_ATTRIBUTE, OTHER).
            description: Description of the wildcard.
        """
        self.name = name
        self.type = type
        self.description = description


class Model(Base):
    """Path to model file."""

    def __init__(self, name: str) -> None:
        """Initialize class.

        Args:
            name: Name of the model file
        """
        super().__init__(name)

    def __eq__(self, other: Model) -> bool:
        """Check if two Model instances are equal.

        Args:
            other: Another Model instance to compare with.

        Returns:
            True if the instances are equal.
        """
        return type(self) is type(other) and self.name == other.name and self.path == other.path

    @property
    def path(self) -> pathlib.Path:
        """Get model path.

        Returns:
            The path to the model file.
        """
        return_path = pathlib.Path(self.name)
        # Return as is if path is absolute, models dir is already included, or if relative path to a file that exists
        if return_path.is_absolute() or paths.models_dir in return_path.parents or return_path.is_file():
            return return_path
        else:
            return paths.models_dir / return_path

    def write(self, data: str) -> None:
        """Write arbitrary string data to models directory.

        Args:
            data: The data to write.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(data, encoding="utf-8")

        # Update file modification time even if nothing was written
        os.utime(self.path, None)
        logger.info("Wrote %d bytes: %s", len(data), self.name)

    def read(self) -> str:
        """Read arbitrary string data from file in models directory.

        Returns:
            The data of the model.
        """
        data = self.path.read_text(encoding="utf-8")
        logger.debug("Read %d bytes: %s", len(data), self.name)
        return data

    def write_pickle(self, data: Any, protocol: int = -1) -> None:
        """Dump arbitrary data to pickle file in models directory.

        Args:
            data: The data to write.
            protocol: Pickle protocol to use.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("wb") as f:
            pickle.dump(data, f, protocol=protocol)
        # Update file modification time even if nothing was written
        os.utime(self.path, None)
        logger.info("Wrote %d bytes: %s", len(data), self.name)

    def read_pickle(self) -> Any:
        """Read pickled data from file in models directory.

        Returns:
            The data of the model.
        """
        with self.path.open("rb") as f:
            data = pickle.load(f)
        logger.debug("Read %d bytes: %s", len(data), self.name)
        return data

    def download(self, url: str) -> None:
        """Download file from URL and save to models directory.

        Args:
            url: URL to download from.
        """
        def log_progress(block_num: int, block_size: int, total_size: int) -> None:
            if total_size > 0:
                logger.progress(progress=block_num * block_size, total=total_size)
        os.makedirs(self.path.parent, exist_ok=True)
        logger.debug("Downloading from: %s", url)
        try:
            urllib.request.urlretrieve(url, self.path, reporthook=log_progress)
            logger.info("Successfully downloaded %s", self.name)
        except Exception as e:
            logger.error("Download of %s from %s failed", self.name, url)
            raise e

    def unzip(self) -> None:
        """Unzip zip file inside models directory."""
        out_dir = self.path.parent
        with zipfile.ZipFile(self.path) as z:
            z.extractall(out_dir)
        logger.info("Successfully unzipped %s", self.name)

    def ungzip(self, out: str) -> None:
        """Unzip gzip file inside modeldir.

        Args:
            out: Path to output file.
        """
        with gzip.open(self.path) as z:
            data = z.read()
            with open(out, "wb") as f:
                f.write(data)
        logger.info("Successfully unzipped %s", out)

    def remove(self, raise_errors: bool = False) -> None:
        """Remove model file from disk.

        Args:
            raise_errors: If True, raise errors if file doesn't exist.
        """
        self.path.unlink(missing_ok=not raise_errors)


class ModelOutput(Model):
    """Path to model file used as output of a modelbuilder."""

    def __init__(self, name: str, description: str | None = None) -> None:
        """Initialize class.

        Args:
            name: Name of the model file.
            description: Description of the model.
        """
        super().__init__(name)
        self.description = description


class Binary(str):
    """Path to binary executable."""


class BinaryDir(str):
    """Path to directory containing executable binaries."""


class Source:
    """Path to directory containing input files."""

    def __init__(self, source_dir: str = "") -> None:
        """Initialize class.

        Args:
            source_dir: Path to directory containing input files. Should usually be left blank, for Sparv to
                automatically get the path.
        """
        self.source_dir = source_dir

    def get_path(self, source_file: SourceFilename, extension: str) -> pathlib.Path:
        """Get the path of a source file.

        Args:
            source_file: Name of the source file.
            extension: File extension to append to the source file.

        Returns:
            The path to the source file.
        """
        if not extension.startswith("."):
            extension = "." + extension
        if ":" in source_file:
            file_name, _, file_chunk = source_file.partition(":")
            source_file = pathlib.Path(self.source_dir, file_name, file_chunk + extension)
        else:
            source_file = pathlib.Path(self.source_dir, source_file + extension)
        return source_file


class Export(str):
    """Export directory and filename pattern."""


class ExportInput(str):
    """Export directory and filename pattern, used as input."""

    def __new__(cls, val: str, *args, **kwargs):
        return super().__new__(cls, val)

    def __init__(self, val: str, all_files: bool = False) -> None:
        """Initialize class.

        Args:
            val: Export directory and filename pattern (e.g. `"xml_export.pretty/[xml_export.filename]"`).
            all_files: Set to `True` to get the export for all source files.
        """
        self.all_files = all_files


class ExportAnnotations(Sequence[tuple[Annotation, str | None]]):
    """Iterable with annotations to include in export."""

    # If is_input = False the annotations won't be added to the rule's input.
    is_input = True

    def __init__(self, config_name: str, is_input: bool | None = None) -> None:
        """Initialize class.

        Args:
            config_name: Name of the config key.
            is_input: Deprecated, use ExportAnnotationNames instead of setting this to False.
        """
        self.config_name = config_name
        self.items = []
        if is_input is not None:
            self.is_input = is_input

    def __getitem__(self, index: int) -> tuple[Annotation, str | None]:
        """Return item at index.

        Each item is a tuple of an Annotation and an optional export name.
        """
        return self.items[index]

    def __len__(self) -> int:
        """Return number of annotations."""
        return len(self.items)


class ExportAnnotationNames(ExportAnnotations):
    """List of annotations to include in export.

    To be used when only the annotation names are of interest and not the actual annotation files.
    """

    is_input = False

    def __init__(self, config_name: str) -> None:
        """Initialize class.

        Args:
            config_name: Name of the config key.
        """
        super().__init__(config_name)


class ExportAnnotationsAllSourceFiles(Sequence[tuple[AnnotationAllSourceFiles, str | None]]):
    """List of annotations to include in export."""

    # Always true for ExportAnnotationsAllSourceFiles
    is_input = True

    def __init__(self, config_name: str) -> None:
        """Initialize class.

        Args:
            config_name: Name of the config key.
        """
        self.config_name = config_name
        self.items: Sequence[tuple[AnnotationAllSourceFiles, str | None]] = []

    def __getitem__(self, index: int) -> tuple[AnnotationAllSourceFiles, str | None]:
        """Return item at index."""
        return self.items[index]

    def __len__(self) -> int:
        """Return number of annotations."""
        return len(self.items)


class SourceAnnotations(Sequence[tuple[Annotation, str | None]]):
    """Iterable with source annotations to include in export."""

    def __init__(self, config_name: str, source_file: str | None = None, _headers: bool = False) -> None:
        """Initialize class.

        Args:
            config_name: Name of the config key.
            source_file: Name of source file.
            _headers: If True, read headers instead of source structure.
        """
        self.config_name = config_name
        self.raw_list = None
        self.annotations: Sequence[tuple[Annotation, str | None]] = []
        self.source_file = source_file
        self.initialized = False
        self.headers = _headers

    def _initialize(self) -> None:
        """Populate class with data."""
        assert self.source_file, "SourceAnnotation is missing source_file"

        # If raw_list is an empty list, don't add any source annotations automatically
        if not self.raw_list and self.raw_list is not None:
            self.initialized = True
            return

        # Parse annotation list and read available source annotations
        if self.headers:
            h = Headers(self.source_file)
            available_source_annotations = h.read() if h.exists() else []
        else:
            available_source_annotations = SourceStructure(self.source_file).read()
        parsed_items = parse_annotation_list(self.raw_list, available_source_annotations)
        # Only include annotations that are available in source
        self.annotations = [
            (Annotation(a[0], self.source_file), a[1]) for a in parsed_items if a[0] in available_source_annotations
        ]
        self.initialized = True

    def __getitem__(self, index: int) -> tuple[Annotation, str | None]:
        """Return item at index."""
        if not self.initialized:
            self._initialize()
        return self.annotations[index]

    def __len__(self) -> int:
        """Return number of annotations."""
        if not self.initialized:
            self._initialize()
        return len(self.annotations)


class HeaderAnnotations(SourceAnnotations):
    """Iterable with header annotations to include in export."""

    def __init__(self, config_name: str, source_file: str | None = None) -> None:
        """Initialize class.

        Args:
            config_name: Name of the config key.
            source_file: Name of source file.
        """
        super().__init__(config_name, source_file, _headers=True)


class SourceAnnotationsAllSourceFiles(Sequence[tuple[AnnotationAllSourceFiles, str | None]]):
    """Iterable with source annotations to include in export."""

    def __init__(self, config_name: str, source_files: Iterable[str] = (), headers: bool = False) -> None:
        """Initialize class.

        Args:
            config_name: Name of the config key.
            source_files: List of source files.
            headers: If True, read headers instead of source structure.
        """
        self.config_name = config_name
        self.raw_list = None
        self.annotations: Sequence[tuple[AnnotationAllSourceFiles, str | None]] = []
        self.source_files = source_files
        self.initialized = False
        self.headers = headers

    def _initialize(self) -> None:
        """Populate class with data."""
        assert self.source_files, "SourceAnnotationsAllSourceFiles is missing source_files"

        # If raw_list is an empty list, don't add any source annotations automatically
        if not self.raw_list and self.raw_list is not None:
            self.initialized = True

        # Parse annotation list and, if needed, read available source annotations
        available_source_annotations = set()
        for f in self.source_files:
            if self.headers:
                h = Headers(f)
                if h.exists():
                    available_source_annotations.update(h.read())
            else:
                available_source_annotations.update(SourceStructure(f).read())

        parsed_items = parse_annotation_list(self.raw_list, available_source_annotations)
        # Only include annotations that are available in source
        self.annotations = [
            (AnnotationAllSourceFiles(a[0]), a[1]) for a in parsed_items if a[0] in available_source_annotations
        ]
        self.initialized = True

    def __getitem__(self, index: int) -> tuple[AnnotationAllSourceFiles, str | None]:
        """Return item at index."""
        if not self.initialized:
            self._initialize()
        return self.annotations[index]

    def __len__(self) -> int:
        """Return number of annotations."""
        if not self.initialized:
            self._initialize()
        return len(self.annotations)


class HeaderAnnotationsAllSourceFiles(SourceAnnotationsAllSourceFiles):
    """Iterable with header annotations to include in export."""

    def __init__(self, config_name: str, source_files: Iterable[str] = ()) -> None:
        """Initialize class.

        Args:
            config_name: Name of the config key.
            source_files: List of source files (internal use only).
        """
        super().__init__(config_name, source_files, headers=True)


class Language(str):
    """Language of the corpus."""


class SourceStructureParser(ABC):
    """Abstract class that should be implemented by an importer's structure parser."""

    def __init__(self, source_dir: pathlib.Path) -> None:
        """Initialize class.

        Args:
            source_dir: Path to corpus source files
        """
        self.answers = {}
        self.source_dir = source_dir

        # Annotations should be saved to this variable after the first scan, and read from here
        # on subsequent calls to the get_annotations() and get_plain_annotations() methods.
        self.annotations = None

    @staticmethod
    def setup() -> dict:
        """Return a list of wizard dictionaries with questions needed for setting up the class.

        Answers to the questions will automatically be saved to self.answers.
        """
        return {}

    @abstractmethod
    def get_annotations(self, corpus_config: dict) -> list[str]:
        """Return a list of annotations including attributes.

        Each value has the format 'annotation:attribute' or 'annotation'.
        Plain versions of each annotation ('annotation' without attribute) must be included as well.
        """

    def get_plain_annotations(self, corpus_config: dict) -> list[str]:
        """Return a list of plain annotations without attributes.

        Each value has the format 'annotation'.
        """
        return [e for e in self.get_annotations(corpus_config) if ":" not in e]
