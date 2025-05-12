"""Pandoc filter for removing links that won't work in PDF and reformatting admonitions.

https://pandoc.org/filters.html
"""

from __future__ import annotations

from typing import Any

from pandocfilters import BlockQuote, Str, Strong, toJSONFilter


def fix_document(key: str, value: str | list | dict | None, _format: str, _meta: dict) -> Any | None:
    """Remove links that won't work in PDF and reformat block quotes."""  # noqa: DOC201
    if key == "Link":
        url = value[2][0]
        if url.startswith(("user-manual", "developers-guide")):
            # Return the link text
            return value[1]
    # Reformat the text inside block quotes
    elif key == "BlockQuote":
        try:
            first_string = value[0]["c"][0]["c"]
            if first_string == "[!NOTE]":
                value[0]["c"][0] = Strong([Str("Note:")])
                return BlockQuote(value)
            if first_string == "[!INFO]":
                value[0]["c"][0] = Strong([Str("Info:")])
                return BlockQuote(value)
            if first_string == "[!TIP]":
                value[0]["c"][0] = Strong([Str("Tip:")])
                return BlockQuote(value)
            if first_string == "[!WARNING]":
                value[0]["c"][0] = Strong([Str("Warning:")])
                return BlockQuote(value)
            if first_string == "[!ATTENTION]":
                value[0]["c"][0] = Strong([Str("Attention:")])
                return BlockQuote(value)
        except Exception:
            return None
    return None


if __name__ == "__main__":
    toJSONFilter(fix_document)
