"""Misc util functions."""

import logging
from typing import List, Optional

from .classes import Annotation
from .constants import Color


class SparvErrorMessage(Exception):
    """Exception used to notify users of errors in a friendly way without displaying traceback."""

    start_marker = "<<<START>>>"
    end_marker = "<<<END>>>"

    def __init__(self, message, module="", function=""):
        """Raise an error and notify user of the problem in a friendly way.

        Args:
            message: Error message.
            module: Name of module where error occurred (optional, not used in Sparv modules)
            function: Name of function where error occurred (optional, not used in Sparv modules)
        """
        self.message = message
        # Alter message before calling base class
        super().__init__("{}{}\n{}\n{}{}".format(SparvErrorMessage.start_marker, module, function, message,
                                                 SparvErrorMessage.end_marker))


def get_logger(name):
    """Get a logger that is a child of 'sparv.modules'."""
    if not name.startswith("sparv.modules"):
        name = "sparv.modules." + name
    return logging.getLogger(name)


def sparv_warning(msg):
    """Format msg into a Sparv warning message."""
    return f"{Color.YELLOW}WARNING: {msg}{Color.RESET}"


def sparv_info(msg):
    """Format msg into a Sparv info message."""
    return f"{Color.GREEN}{msg}{Color.RESET}"


def _safe_join(sep, elems):
    """Join a list of strings (elems), using (sep) as separator.

    All occurrences of (sep) in (elems) are removed.
    """
    return sep.join(elem.replace(sep, "") for elem in elems)


def strtobool(value):
    """Convert possible string to boolean."""
    if isinstance(value, str):
        value = (value.lower() == "true")
    return value


def split(value):
    """If 'value' is a string, split and return a list, otherwise return as is."""
    if isinstance(value, str):
        value = value.split()
    return value


def parse_annotation_list(annotation_names: Optional[List[str]], add_plain_annotations: bool = True):
    """Take a list of annotation names and possible export names, and return a list of tuples.

    Each list item will be split into a tuple by the string ' as '.
    Each tuple will contain 2 elements. If there is no ' as ' in the string, the second element will be None.

    Plain annotations (without attributes) will be added if needed, unless add_plain_annotations is set to False.
    Make sure to disable add_plain_annotations if the annotation names may include classes or config variables.
    """
    if not annotation_names:
        return []
    plain_annotations = set()
    possible_plain_annotations = set()
    result = []
    for a in annotation_names:
        name, _, export_name = a.partition(" as ")
        plain_name, attr = Annotation(name).split()
        if not attr:
            plain_annotations.add(name)
        else:
            possible_plain_annotations.add(plain_name)
        result.append((name, export_name or None))

    if add_plain_annotations:
        for a in possible_plain_annotations.difference(plain_annotations):
            result.append((a, None))

    return result


def single_true(iterable):
    """Return True if one and only one element in iterable evaluates to True."""
    i = iter(iterable)
    return any(i) and not any(i)


def cwbset(values, delimiter="|", affix="|", sort=False, maxlength=4095, encoding="UTF-8"):
    """Take an iterable object and return a set in the format used by Corpus Workbench."""
    values = list(values)
    if sort:
        values.sort()
    if maxlength:
        length = 1  # Including the last affix
        for i, value in enumerate(values):
            length += len(value.encode(encoding)) + 1
            if length > maxlength:
                values = values[:i]
                break
    return affix if not values else affix + delimiter.join(values) + affix


def cwbset_to_list(cwbset, delimiter="|", affix="|"):
    """Turn a cwbset string into a list."""
    cwbset = cwbset.strip(affix)
    return cwbset.split(delimiter)


def truncateset(string, maxlength=4095, delimiter="|", affix="|", encoding="UTF-8"):
    """Truncate a Corpus Workbench set to a maximum length."""
    if len(string) <= maxlength or string == "|":
        return string
    else:
        length = 1  # Including the last affix
        values = string[1:-1].split("|")
        for i, value in enumerate(values):
            length += len(value.encode(encoding)) + 1
            if length > maxlength:
                return cwbset(values[:i], delimiter, affix)


def remove_control_characters(text):
    """Remove control characters from text."""
    return text.translate(dict(
        (ord(c), None) for c in [chr(i) for i in list(range(9)) + list(range(11, 13)) + list(range(14, 32)) + [127]]))
