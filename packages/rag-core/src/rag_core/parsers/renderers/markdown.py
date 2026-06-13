"""Markdown rendering utilities for parsed documents and elements."""

import re
from html.parser import HTMLParser

from rag_core.parsers.renderers.text import _html_to_text
from rag_core.parsers.schemas import ContentFormat, ElementType, ParsedDocument, ParsedElement


def _ordered_elements(document: ParsedDocument, *, include_ignored: bool = False) -> list[ParsedElement]:
    """Helper to return document elements sorted by their sequence order."""
    elements = document.elements
    if not include_ignored:
        elements = [element for element in elements if not element.ignored]
    return sorted(elements, key=lambda element: element.order)


def _strip_markdown_heading(content: str) -> str:
    """Strips leading markdown heading hash marks."""
    return re.sub(r"^#{1,6}\s+", "", content.strip())


def _safe_heading_level(level: int | None) -> int:
    """Clamps heading levels to valid HTML levels 1-6."""
    return min(max(level or 1, 1), 6)


def _escape_markdown_alt(value: str) -> str:
    """Escapes brackets in markdown alt text."""
    return value.replace("[", r"\[").replace("]", r"\]")


def _asset_source(element: ParsedElement) -> str:
    """Resolves target source path/URI for elements referencing assets."""
    if element.asset is None:
        return element.content.strip() if element.format == ContentFormat.ASSET_REF else ""
    return element.asset.uri or element.asset.path or ""


def _image_alt(element: ParsedElement) -> str:
    """Extracts alternative text for image elements."""
    alt = element.metadata.get("alt") or element.metadata.get("caption") or element.content.strip()
    return str(alt) if alt is not None else ""


class _HTMLTableParser(HTMLParser):
    """HTML Table parser to extract rows and columns structure from fragments."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None

    @classmethod
    def parse(cls, html: str) -> list[list[str]]:
        parser = cls()
        parser.feed(html)
        parser.close()
        return parser.rows

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._current_row = []
        elif tag in {"td", "th"} and self._current_row is not None:
            self._current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._current_row is not None and self._current_cell is not None:
            self._current_row.append(" ".join("".join(self._current_cell).split()))
            self._current_cell = None
        elif tag == "tr" and self._current_row is not None:
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = None

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)


def _markdown_table_row(cells: list[str]) -> str:
    """Formats a list of cell contents into a markdown table row string."""
    escaped = [cell.replace("|", r"\|").replace("\n", " ") for cell in cells]
    return f"| {' | '.join(escaped)} |"


def _html_table_to_markdown(html: str) -> str:
    """Converts an HTML table fragment to markdown format."""
    rows = _HTMLTableParser.parse(html)
    if not rows:
        return _html_to_text(html)

    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    header = normalized[0]
    separator = ["---"] * width
    body = normalized[1:]
    markdown_rows = [_markdown_table_row(header), _markdown_table_row(separator)]
    markdown_rows.extend(_markdown_table_row(row) for row in body)
    return "\n".join(markdown_rows)


def _image_to_markdown(element: ParsedElement) -> str:
    """Renders a parsed image element to markdown alt/source syntax."""
    source = _asset_source(element)
    if not source:
        return element.content.strip()
    alt = _image_alt(element)
    return f"![{_escape_markdown_alt(alt)}]({source})"


def _markdown_heading(element: ParsedElement) -> str:
    content = element.content.strip()
    text = _strip_markdown_heading(content)
    level = _safe_heading_level(element.level)
    return f"{'#' * level} {text}" if text else ""


def _markdown_table(element: ParsedElement) -> str:
    content = element.content.strip()
    if element.format == ContentFormat.HTML:
        return _html_table_to_markdown(content)
    return content


def _markdown_image(element: ParsedElement) -> str:
    return _image_to_markdown(element)


def _markdown_equation(element: ParsedElement) -> str:
    content = element.content.strip()
    return f"$$\n{content}\n$$" if content and element.format == ContentFormat.LATEX else content


def _markdown_caption(element: ParsedElement) -> str:
    content = element.content.strip()
    return f"*{content}*" if content else ""


def _markdown_code(element: ParsedElement) -> str:
    content = element.content.strip()
    return f"```\n{content}\n```" if content else ""


_MARKDOWN_ELEMENT_RENDERERS = {
    ElementType.HEADING: _markdown_heading,
    ElementType.TABLE: _markdown_table,
    ElementType.IMAGE: _markdown_image,
    ElementType.EQUATION: _markdown_equation,
    ElementType.CAPTION: _markdown_caption,
    ElementType.CODE: _markdown_code,
}


def _element_to_markdown(element: ParsedElement) -> str:
    """Renders an individual parsed element into markdown."""
    renderer = _MARKDOWN_ELEMENT_RENDERERS.get(element.type)
    if renderer:
        return renderer(element)

    content = element.content.strip()
    if element.format == ContentFormat.HTML:
        return _html_to_text(content)
    if element.format == ContentFormat.ASSET_REF:
        return _image_to_markdown(element)
    if element.format == ContentFormat.LATEX and content:
        return f"$$\n{content}\n$$"
    return content


def parsed_document_to_markdown(
    document: ParsedDocument, *, prefer_document: bool = False, include_ignored: bool = False
) -> str:
    """Return Markdown for a parsed document.

    By default, output is reconstructed from `document.elements` so previews
    match the canonical data used by downstream RAG code. Set
    `prefer_document=True` to prefer parser-provided document-level Markdown.

    Args:
        document: The ParsedDocument instance to serialize.
        prefer_document: If True, uses the document-level raw markdown if present.
        include_ignored: If True, includes elements marked as ignored.

    Returns:
        str: Reconstructed markdown text.
    """
    if prefer_document and document.markdown.strip():
        return document.markdown

    rendered = [
        _element_to_markdown(element) for element in _ordered_elements(document, include_ignored=include_ignored)
    ]
    markdown = "\n\n".join(block for block in rendered if block.strip()).strip()
    if markdown:
        return markdown

    if document.markdown.strip():
        return document.markdown
    if document.text.strip():
        return document.text
    if document.html.strip():
        return _html_to_text(document.html)
    return ""


def to_markdown(document: ParsedDocument, *, prefer_document: bool = False, include_ignored: bool = False) -> str:
    """Short alias for `parsed_document_to_markdown`."""
    return parsed_document_to_markdown(document, prefer_document=prefer_document, include_ignored=include_ignored)
