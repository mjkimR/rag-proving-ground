"""Render ParsedDocument instances into exchange formats.

These helpers render normalized elements first because elements are the
canonical data consumed downstream. Parser-provided document-level formats are
used as fallbacks when elements cannot produce output.
"""

import re
from html import escape
from html.parser import HTMLParser
from typing import ClassVar

from rag_core.parsers.schemas import ContentFormat, ElementType, ParsedDocument, ParsedElement


def parsed_document_to_markdown(document: ParsedDocument, *, prefer_document: bool = False) -> str:
    """Return Markdown for a parsed document.

    By default, output is reconstructed from `document.elements` so previews
    match the canonical data used by downstream RAG code. Set
    `prefer_document=True` to prefer parser-provided document-level Markdown.
    """

    if prefer_document and document.markdown.strip():
        return document.markdown

    rendered = [_element_to_markdown(element) for element in _ordered_elements(document)]
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


def parsed_document_to_html(
    document: ParsedDocument, *, prefer_document: bool = False, title: str | None = None
) -> str:
    """Return HTML for a parsed document.

    The returned value is a fragment unless `title` is supplied, in which case a
    minimal complete HTML document is returned. Elements are rendered first by
    default; parser-provided document-level HTML is a fallback.
    """

    if prefer_document and document.html.strip():
        return document.html

    rendered = [_element_to_html(element) for element in _ordered_elements(document)]
    html = "\n".join(block for block in rendered if block.strip()).strip()
    if not html and document.html.strip():
        html = document.html
    if not html and document.markdown.strip():
        html = _markdown_to_html(document.markdown)
    if not html and document.text.strip():
        html = _paragraph_to_html(document.text)

    if title is None:
        return html

    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        f"  <title>{escape(title)}</title>\n"
        "</head>\n"
        f"<body>\n{html}\n</body>\n"
        "</html>"
    )


def to_markdown(document: ParsedDocument, *, prefer_document: bool = False) -> str:
    """Short alias for `parsed_document_to_markdown`."""

    return parsed_document_to_markdown(document, prefer_document=prefer_document)


def to_html(document: ParsedDocument, *, prefer_document: bool = False, title: str | None = None) -> str:
    """Short alias for `parsed_document_to_html`."""

    return parsed_document_to_html(document, prefer_document=prefer_document, title=title)


def _ordered_elements(document: ParsedDocument) -> list[ParsedElement]:
    return sorted(document.elements, key=lambda element: element.order)


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


_MARKDOWN_ELEMENT_RENDERERS = {
    ElementType.HEADING: _markdown_heading,
    ElementType.TABLE: _markdown_table,
    ElementType.IMAGE: _markdown_image,
    ElementType.EQUATION: _markdown_equation,
    ElementType.CAPTION: _markdown_caption,
}


def _element_to_markdown(element: ParsedElement) -> str:
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


def _html_heading(element: ParsedElement) -> str:
    content = element.content.strip()
    text = _strip_markdown_heading(content)
    level = _safe_heading_level(element.level)
    return f"<h{level}>{escape(text)}</h{level}>" if text else ""


def _html_list(element: ParsedElement) -> str:
    content = element.content.strip()
    return _markdown_list_to_html(content)


def _html_list_item(element: ParsedElement) -> str:
    content = element.content.strip()
    item = _strip_list_marker(content)
    return f"<ul><li>{escape(item)}</li></ul>" if item else ""


def _html_table(element: ParsedElement) -> str:
    content = element.content.strip()
    if element.format == ContentFormat.HTML:
        return content
    return _markdown_table_to_html(content)


def _html_image(element: ParsedElement) -> str:
    return _image_to_html(element)


def _html_equation(element: ParsedElement) -> str:
    content = element.content.strip()
    return f'<pre><code class="language-latex">{escape(content)}</code></pre>' if content else ""


def _html_caption(element: ParsedElement) -> str:
    content = element.content.strip()
    return f"<p><em>{escape(content)}</em></p>" if content else ""


_HTML_ELEMENT_RENDERERS = {
    ElementType.HEADING: _html_heading,
    ElementType.LIST: _html_list,
    ElementType.LIST_ITEM: _html_list_item,
    ElementType.TABLE: _html_table,
    ElementType.IMAGE: _html_image,
    ElementType.EQUATION: _html_equation,
    ElementType.CAPTION: _html_caption,
}


def _element_to_html(element: ParsedElement) -> str:
    renderer = _HTML_ELEMENT_RENDERERS.get(element.type)
    if renderer:
        return renderer(element)

    content = element.content.strip()
    if element.format == ContentFormat.HTML:
        return content
    if element.format == ContentFormat.LATEX:
        return f'<pre><code class="language-latex">{escape(content)}</code></pre>' if content else ""
    return _paragraph_to_html(content)


def _image_to_markdown(element: ParsedElement) -> str:
    source = _asset_source(element)
    if not source:
        return element.content.strip()
    alt = _image_alt(element)
    return f"![{_escape_markdown_alt(alt)}]({source})"


def _image_to_html(element: ParsedElement) -> str:
    source = _asset_source(element)
    if not source:
        return _paragraph_to_html(element.content.strip())
    alt = _image_alt(element)
    img = f'<img src="{escape(source, quote=True)}" alt="{escape(alt, quote=True)}">'
    caption = element.content.strip()
    if caption:
        return f"<figure>{img}<figcaption>{escape(caption)}</figcaption></figure>"
    return img


def _asset_source(element: ParsedElement) -> str:
    if element.asset is None:
        return element.content.strip() if element.format == ContentFormat.ASSET_REF else ""
    return element.asset.uri or element.asset.path or ""


def _image_alt(element: ParsedElement) -> str:
    alt = element.metadata.get("alt") or element.metadata.get("caption") or element.content.strip()
    return str(alt) if alt is not None else ""


def _paragraph_to_html(content: str) -> str:
    blocks = [block.strip() for block in content.split("\n\n") if block.strip()]
    return "\n".join(f"<p>{escape(block).replace(chr(10), '<br>')}</p>" for block in blocks)


def _markdown_to_html(markdown: str) -> str:
    blocks = [block.strip() for block in markdown.split("\n\n") if block.strip()]
    rendered: list[str] = []
    for block in blocks:
        heading = re.match(r"^(#{1,6})\s+(.+)$", block)
        if heading:
            level = len(heading.group(1))
            rendered.append(f"<h{level}>{escape(heading.group(2).strip())}</h{level}>")
        elif _looks_like_markdown_table(block):
            rendered.append(_markdown_table_to_html(block))
        elif _looks_like_markdown_list(block):
            rendered.append(_markdown_list_to_html(block))
        elif block.startswith("!["):
            rendered.append(_markdown_image_to_html(block))
        else:
            rendered.append(_paragraph_to_html(block))
    return "\n".join(rendered)


def _markdown_list_to_html(markdown: str) -> str:
    items: list[str] = []
    ordered = False
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        ordered_match = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        unordered_match = re.match(r"^[-*+]\s+(.+)$", stripped)
        if ordered_match:
            ordered = True
            items.append(ordered_match.group(1).strip())
        elif unordered_match:
            items.append(unordered_match.group(1).strip())
        else:
            items.append(stripped)

    if not items:
        return ""

    tag = "ol" if ordered else "ul"
    body = "".join(f"<li>{escape(item)}</li>" for item in items)
    return f"<{tag}>{body}</{tag}>"


def _markdown_table_to_html(markdown: str) -> str:
    rows = _markdown_table_rows(markdown)
    if not rows:
        return _paragraph_to_html(markdown)

    has_header = len(rows) > 1 and _is_markdown_separator_row(rows[1])
    header = rows[0] if has_header else []
    body_rows = rows[2:] if has_header else rows
    parts = ["<table>"]
    if header:
        cells = "".join(f"<th>{escape(cell)}</th>" for cell in header)
        parts.append(f"  <thead><tr>{cells}</tr></thead>")
    if body_rows:
        parts.append("  <tbody>")
        for row in body_rows:
            cells = "".join(f"<td>{escape(cell)}</td>" for cell in row)
            parts.append(f"    <tr>{cells}</tr>")
        parts.append("  </tbody>")
    parts.append("</table>")
    return "\n".join(parts)


def _html_table_to_markdown(html: str) -> str:
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


def _markdown_table_rows(markdown: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if "|" not in stripped:
            continue
        if stripped.startswith("|"):
            stripped = stripped[1:]
        if stripped.endswith("|"):
            stripped = stripped[:-1]
        rows.append([cell.strip() for cell in stripped.split("|")])
    return rows


def _markdown_table_row(cells: list[str]) -> str:
    escaped = [cell.replace("|", r"\|").replace("\n", " ") for cell in cells]
    return f"| {' | '.join(escaped)} |"


def _is_markdown_separator_row(row: list[str]) -> bool:
    return all(re.fullmatch(r":?-{3,}:?", cell.strip()) is not None for cell in row)


def _looks_like_markdown_table(block: str) -> bool:
    rows = _markdown_table_rows(block)
    return len(rows) >= 2 and _is_markdown_separator_row(rows[1])


def _looks_like_markdown_list(block: str) -> bool:
    return all(re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", line) for line in block.splitlines() if line.strip())


def _markdown_image_to_html(markdown: str) -> str:
    match = re.match(r'^!\[([^]]*)]\(([^)\s]+)(?:\s+"[^"]*")?\)$', markdown.strip())
    if not match:
        return _paragraph_to_html(markdown)
    alt, source = match.groups()
    return f'<img src="{escape(source, quote=True)}" alt="{escape(alt, quote=True)}">'


def _html_to_text(html: str) -> str:
    return _HTMLTextParser.parse(html)


def _strip_markdown_heading(content: str) -> str:
    return re.sub(r"^#{1,6}\s+", "", content.strip())


def _strip_list_marker(content: str) -> str:
    return re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", content.strip())


def _safe_heading_level(level: int | None) -> int:
    return min(max(level or 1, 1), 6)


def _escape_markdown_alt(value: str) -> str:
    return value.replace("[", r"\[").replace("]", r"\]")


class _HTMLTableParser(HTMLParser):
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
