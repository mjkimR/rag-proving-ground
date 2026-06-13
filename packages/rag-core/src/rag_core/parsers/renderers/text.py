"""Text rendering and HTML parsing utilities for parsed documents."""

import re
from html.parser import HTMLParser
from typing import ClassVar


def _escape_markdown_alt(value: str) -> str:
    """Escapes markdown alt text brackets."""
    return value.replace("[", r"\[").replace("]", r"\]")


class _HTMLTextParser(HTMLParser):
    _BLOCK_TAGS: ClassVar[set[str]] = {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "div",
        "figcaption",
        "h1",
        "h2",
        "h3",
        "h4",
    }
    _BLOCK_TAGS |= {"h5", "h6", "li", "p", "section", "td", "th", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    @classmethod
    def parse(cls, html: str) -> str:
        parser = cls()
        parser.feed(html)
        parser.close()
        return re.sub(r"\n{3,}", "\n\n", "".join(parser.parts)).strip()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "img":
            attrs_dict = dict(attrs)
            source = attrs_dict.get("src") or ""
            alt = attrs_dict.get("alt") or ""
            if source:
                self.parts.append(f"![{_escape_markdown_alt(alt)}]({source})")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if stripped:
            self.parts.append(stripped)
            self.parts.append(" ")


def _html_to_text(html: str) -> str:
    """Extracts raw text from an HTML fragment, preserving block boundaries."""
    return _HTMLTextParser.parse(html)
