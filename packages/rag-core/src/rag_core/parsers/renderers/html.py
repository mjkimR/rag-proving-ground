"""HTML rendering utilities for parsed documents and elements."""

import re
from html import escape

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


def _strip_list_marker(content: str) -> str:
    """Strips markdown list bullets or numbers from text."""
    return re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", content.strip())


def _asset_source(element: ParsedElement) -> str:
    """Resolves target source path/URI for elements referencing assets."""
    if element.asset is None:
        return element.content.strip() if element.format == ContentFormat.ASSET_REF else ""
    return element.asset.uri or element.asset.path or ""


def _image_alt(element: ParsedElement) -> str:
    """Extracts alternative text for image elements."""
    alt = element.metadata.get("alt") or element.metadata.get("caption") or element.content.strip()
    return str(alt) if alt is not None else ""


def _paragraph_to_html(content: str) -> str:
    """Converts a multi-paragraph text block into paragraph tags."""
    blocks = [block.strip() for block in content.split("\n\n") if block.strip()]
    return "\n".join(f"<p>{escape(block).replace(chr(10), '<br>')}</p>" for block in blocks)


def _markdown_list_to_html(markdown: str) -> str:
    """Renders a markdown list string (numbered or bulleted) into HTML tags."""
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


def _markdown_table_rows(markdown: str) -> list[list[str]]:
    """Helper to parse raw markdown table pipe syntax into rows of cells."""
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


def _is_markdown_separator_row(row: list[str]) -> bool:
    """Returns True if the row matches separator pipes (e.g. `---`)."""
    return all(re.fullmatch(r":?-{3,}:?", cell.strip()) is not None for cell in row)


def _looks_like_markdown_table(block: str) -> bool:
    """Returns True if the text block matches basic markdown table syntax."""
    rows = _markdown_table_rows(block)
    return len(rows) >= 2 and _is_markdown_separator_row(rows[1])


def _looks_like_markdown_list(block: str) -> bool:
    """Returns True if the block lines start with list indicators."""
    return all(re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", line) for line in block.splitlines() if line.strip())


def _markdown_table_to_html(markdown: str) -> str:
    """Translates a markdown table block to an HTML table."""
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


def _markdown_image_to_html(markdown: str) -> str:
    """Translates markdown image syntax into an HTML img tag."""
    match = re.match(r'^!\[([^]]*)]\(([^)\s]+)(?:\s+"[^"]*")?\)$', markdown.strip())
    if not match:
        return _paragraph_to_html(markdown)
    alt, source = match.groups()
    return f'<img src="{escape(source, quote=True)}" alt="{escape(alt, quote=True)}">'


def _markdown_to_html(markdown: str) -> str:
    """Converts a broad markdown string block into HTML elements."""
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


def _image_to_html(element: ParsedElement) -> str:
    """Converts a parsed image element to HTML img tags, wrapping captions in figure/figcaption."""
    source = _asset_source(element)
    if not source:
        return _paragraph_to_html(element.content.strip())
    alt = _image_alt(element)
    img = f'<img src="{escape(source, quote=True)}" alt="{escape(alt, quote=True)}">'
    caption = element.content.strip()
    if caption:
        return f"<figure>{img}<figcaption>{escape(caption)}</figcaption></figure>"
    return img


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


def _html_code(element: ParsedElement) -> str:
    content = element.content.strip()
    return f"<pre><code>{escape(content)}</code></pre>" if content else ""


_HTML_ELEMENT_RENDERERS = {
    ElementType.HEADING: _html_heading,
    ElementType.LIST: _html_list,
    ElementType.LIST_ITEM: _html_list_item,
    ElementType.TABLE: _html_table,
    ElementType.IMAGE: _html_image,
    ElementType.EQUATION: _html_equation,
    ElementType.CAPTION: _html_caption,
    ElementType.CODE: _html_code,
}


def _element_to_html(element: ParsedElement) -> str:
    """Renders an individual element to HTML."""
    renderer = _HTML_ELEMENT_RENDERERS.get(element.type)
    if renderer:
        return renderer(element)

    content = element.content.strip()
    if element.format == ContentFormat.HTML:
        return content
    if element.format == ContentFormat.LATEX:
        return f'<pre><code class="language-latex">{escape(content)}</code></pre>' if content else ""
    return _paragraph_to_html(content)


def parsed_document_to_html(
    document: ParsedDocument,
    *,
    prefer_document: bool = False,
    title: str | None = None,
    include_ignored: bool = False,
) -> str:
    """Return HTML for a parsed document.

    The returned value is a fragment unless `title` is supplied, in which case a
    minimal complete HTML document is returned. Elements are rendered first by
    default; parser-provided document-level HTML is a fallback.

    Args:
        document: The ParsedDocument instance.
        prefer_document: If True, uses the document-level raw HTML if present.
        title: Optional title string to wrap output inside a complete HTML page.
        include_ignored: If True, includes elements marked as ignored.

    Returns:
        str: Reconstructed HTML text.
    """
    if prefer_document and document.html.strip():
        return document.html

    rendered = [_element_to_html(element) for element in _ordered_elements(document, include_ignored=include_ignored)]
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


def to_html(
    document: ParsedDocument,
    *,
    prefer_document: bool = False,
    title: str | None = None,
    include_ignored: bool = False,
) -> str:
    """Short alias for `parsed_document_to_html`."""
    return parsed_document_to_html(
        document, prefer_document=prefer_document, title=title, include_ignored=include_ignored
    )
