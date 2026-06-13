import re
from html import escape
from pathlib import Path
from typing import ClassVar

import httpx
from loguru import logger
from markdown_it import MarkdownIt

from rag_core.adapters.parser.interface import Parser, ParserInput
from rag_core.config import get_native_text_parser_settings
from rag_core.parsers.schemas import (
    PARSED_DOCUMENT_SCHEMA_VERSION,
    ContentFormat,
    ElementType,
    ParsedDocument,
    ParsedElement,
    ParsedPage,
)

from ..shared.network_security import _validate_ssrf, get_safe_http_client
from .html_parser import HTMLToElementsParser


class NativeTextParser(Parser):
    """Local native parser for text, Markdown, and HTML documents."""

    name: ClassVar[str] = "native_text"
    schema_version: ClassVar[str] = PARSED_DOCUMENT_SCHEMA_VERSION

    def __init__(self, max_page_chars: int = 2000) -> None:
        self.max_page_chars = max_page_chars

    @classmethod
    def from_config(cls) -> "NativeTextParser":
        settings = get_native_text_parser_settings()
        return cls(max_page_chars=settings.max_page_chars)

    async def parse(self, parser_input: ParserInput) -> ParsedDocument:
        # Determine document ID
        doc_id = parser_input.metadata.get("doc_id")
        if not doc_id:
            source = parser_input.source or parser_input.filename or "document"
            doc_id = Path(source).stem or source

        # Load content string
        content_str = await self._get_content_string(parser_input)

        # Detect mimetype/extension to dispatch parser
        filename = parser_input.filename or ""
        mimetype = parser_input.content_type or ""

        elements: list[ParsedElement] = []

        try:
            if filename.endswith((".html", ".htm")) or mimetype == "text/html":
                elements = self._parse_html(content_str, doc_id)
            elif filename.endswith((".md", ".markdown")) or mimetype in ("text/markdown", "text/x-markdown"):
                elements = self._parse_markdown(content_str, doc_id)
            else:
                # Default to plain text
                elements = self._parse_plain_text(content_str, doc_id)
        except Exception as exc:
            logger.exception(f"Parsing failed for {filename}. Falling back to single paragraph. Error: {exc}")
            # Fallback to single paragraph
            elements = [
                ParsedElement(
                    element_id=f"{doc_id}_el_fallback",
                    type=ElementType.PARAGRAPH,
                    format=ContentFormat.TEXT,
                    content=content_str,
                    order=0,
                )
            ]

        # Ensure order is sequentially correct
        for idx, el in enumerate(elements):
            el.order = idx

        # Generate synthetic pages
        pages, elements = self._assign_synthetic_pages(elements, doc_id)

        # Construct ParsedDocument
        parsed_doc = ParsedDocument(
            doc_id=doc_id,
            source=parser_input.source,
            filename=parser_input.filename,
            mimetype=parser_input.content_type,
            parser=self.name,
            pages=pages,
            elements=elements,
        )

        return parsed_doc

    async def _get_content_string(self, parser_input: ParserInput) -> str:
        if parser_input.content is not None:
            try:
                return parser_input.content.decode("utf-8")
            except UnicodeDecodeError:
                return parser_input.content.decode("latin-1")

        if parser_input.source:
            if parser_input.source.startswith(("http://", "https://")):
                _validate_ssrf(parser_input.source)
                client = get_safe_http_client()
                try:
                    # Limit size to 10MB and set explicit timeout of 15.0 seconds
                    async with client.stream("GET", parser_input.source, timeout=15.0) as response:
                        response.raise_for_status()

                        content_length = response.headers.get("Content-Length")
                        if content_length is not None and int(content_length) > 10 * 1024 * 1024:
                            raise ValueError("Content length exceeds maximum limit of 10MB")

                        content_bytes = bytearray()
                        async for chunk in response.aiter_bytes(chunk_size=16384):
                            content_bytes.extend(chunk)
                            if len(content_bytes) > 10 * 1024 * 1024:
                                raise ValueError("Content size exceeds limit of 10MB")

                        try:
                            return content_bytes.decode("utf-8")
                        except UnicodeDecodeError:
                            return content_bytes.decode("latin-1")
                except httpx.TimeoutException as exc:
                    logger.error(f"Timeout requesting remote resource {parser_input.source}: {exc}")
                    raise RuntimeError(f"Network Timeout: Failed to fetch remote resource: {exc}") from exc
                except httpx.NetworkError as exc:
                    logger.error(f"Network error requesting remote resource {parser_input.source}: {exc}")
                    raise RuntimeError(f"Network Error: Failed to fetch remote resource: {exc}") from exc
                except httpx.HTTPStatusError as exc:
                    logger.error(f"HTTP status error for remote resource {parser_input.source}: {exc}")
                    raise exc
                except httpx.HTTPError as exc:
                    logger.error(f"HTTP error requesting remote resource {parser_input.source}: {exc}")
                    raise exc
            else:
                import anyio

                path = anyio.Path(parser_input.source)
                return await path.read_text(encoding="utf-8", errors="replace")

        raise ValueError("ParserInput has neither content nor source.")

    def _parse_plain_text(self, text: str, doc_id: str) -> list[ParsedElement]:
        elements = []
        # Support both UNIX (\n) and Windows (\r\n) line endings
        blocks = [block.strip() for block in re.split(r"\r?\n\s*\r?\n", text) if block.strip()]
        for block in blocks:
            elements.append(
                ParsedElement(
                    element_id=f"{doc_id}_el_{len(elements)}",
                    type=ElementType.PARAGRAPH,
                    format=ContentFormat.TEXT,
                    content=block,
                    order=len(elements),
                )
            )
        return elements

    def _parse_markdown(self, text: str, doc_id: str) -> list[ParsedElement]:
        md = MarkdownIt("default", {"html": True})
        tokens = md.parse(text)
        elements: list[ParsedElement] = []

        current_type = None  # None, "heading", "list", "table", "paragraph"
        heading_level = 1
        heading_content = ""
        paragraph_content = ""
        list_items: list[tuple[str, str]] = []
        list_nesting_level = 0
        list_type = None
        list_item_content = ""
        list_item_nesting = 0
        in_list_item = False

        table_html: list[str] = []
        table_nesting_level = 0
        in_table_cell = False
        cell_tag = ""
        cell_content = ""
        cell_nesting = 0

        for token in tokens:
            if current_type == "table":
                if token.type == "table_close" and token.level == table_nesting_level:
                    table_html.append("</table>")
                    elements.append(
                        ParsedElement(
                            element_id=f"{doc_id}_el_{len(elements)}",
                            type=ElementType.TABLE,
                            format=ContentFormat.HTML,
                            content="\n".join(table_html),
                            order=len(elements),
                        )
                    )
                    current_type = None
                    # Reset table state variables
                    table_html = []
                    table_nesting_level = 0
                    in_table_cell = False
                    cell_tag = ""
                    cell_content = ""
                    cell_nesting = 0

                elif token.type in ("thead_open", "tbody_open", "tr_open"):
                    table_html.append(f"<{token.tag}>")
                elif token.type in ("thead_close", "tbody_close", "tr_close"):
                    table_html.append(f"</{token.tag}>")
                elif token.type in ("th_open", "td_open"):
                    in_table_cell = True
                    cell_tag = token.tag
                    cell_content = ""
                    cell_nesting = token.level
                elif token.type in ("th_close", "td_close") and token.level == cell_nesting:
                    table_html.append(f"<{cell_tag}>{escape(cell_content.strip())}</{cell_tag}>")
                    in_table_cell = False
                elif in_table_cell and token.type == "inline":
                    cell_content += token.content
                continue

            if current_type == "list":
                if token.type in ("bullet_list_close", "ordered_list_close") and token.level == list_nesting_level:
                    rendered_items = []
                    for idx, (item_text, ltype) in enumerate(list_items, start=1):
                        prefix = f"{idx}. " if ltype == "ordered_list_open" else "- "
                        rendered_items.append(f"{prefix}{item_text}")
                    list_markdown = "\n".join(rendered_items)
                    elements.append(
                        ParsedElement(
                            element_id=f"{doc_id}_el_{len(elements)}",
                            type=ElementType.LIST,
                            format=ContentFormat.MARKDOWN,
                            content=list_markdown,
                            order=len(elements),
                        )
                    )
                    current_type = None
                    # Reset list state variables
                    list_items = []
                    list_nesting_level = 0
                    list_type = None
                    list_item_content = ""
                    list_item_nesting = 0
                    in_list_item = False

                elif token.type == "list_item_open":
                    in_list_item = True
                    list_item_content = ""
                    list_item_nesting = token.level
                elif token.type == "list_item_close" and token.level == list_item_nesting:
                    if list_type:
                        list_items.append((list_item_content.strip(), list_type))
                    in_list_item = False
                elif in_list_item:
                    if token.type == "inline":
                        list_item_content += token.content
                    elif token.type == "fence":
                        list_item_content += f"\n```{token.info or ''}\n{token.content}```\n"
                continue

            if current_type == "heading":
                if token.type == "heading_close":
                    elements.append(
                        ParsedElement(
                            element_id=f"{doc_id}_el_{len(elements)}",
                            type=ElementType.HEADING,
                            format=ContentFormat.MARKDOWN,
                            content=heading_content.strip(),
                            level=heading_level,
                            order=len(elements),
                        )
                    )
                    current_type = None
                elif token.type == "inline":
                    heading_content += token.content
                continue

            if current_type == "paragraph":
                if token.type == "paragraph_close":
                    if paragraph_content.strip():
                        elements.append(
                            ParsedElement(
                                element_id=f"{doc_id}_el_{len(elements)}",
                                type=ElementType.PARAGRAPH,
                                format=ContentFormat.MARKDOWN,
                                content=paragraph_content.strip(),
                                order=len(elements),
                            )
                        )
                    current_type = None
                elif token.type == "inline":
                    paragraph_content += token.content
                continue

            # Start of block tags
            if token.type == "heading_open":
                current_type = "heading"
                heading_level = int(token.tag[1]) if (token.tag and token.tag[1].isdigit()) else 1
                heading_content = ""
            elif token.type in ("bullet_list_open", "ordered_list_open"):
                current_type = "list"
                list_type = token.type
                list_items = []
                list_nesting_level = token.level
                list_item_content = ""
                list_item_nesting = 0
                in_list_item = False
            elif token.type == "table_open":
                current_type = "table"
                table_html = ["<table>"]
                table_nesting_level = token.level
                in_table_cell = False
                cell_tag = ""
                cell_content = ""
                cell_nesting = 0
            elif token.type in ("fence", "code_block"):
                code_markdown = f"```{token.info or ''}\n{token.content}```"
                elements.append(
                    ParsedElement(
                        element_id=f"{doc_id}_el_{len(elements)}",
                        type=ElementType.PARAGRAPH,
                        format=ContentFormat.MARKDOWN,
                        content=code_markdown,
                        order=len(elements),
                    )
                )
            elif token.type == "html_block":
                if token.content.strip():
                    elements.append(
                        ParsedElement(
                            element_id=f"{doc_id}_el_{len(elements)}",
                            type=ElementType.PARAGRAPH,
                            format=ContentFormat.HTML,
                            content=token.content.strip(),
                            order=len(elements),
                        )
                    )
            elif token.type == "paragraph_open":
                current_type = "paragraph"
                paragraph_content = ""
            elif token.type == "inline":
                # Only parse as a separate paragraph if we are not inside another block context
                if current_type is None and token.content.strip():
                    elements.append(
                        ParsedElement(
                            element_id=f"{doc_id}_el_{len(elements)}",
                            type=ElementType.PARAGRAPH,
                            format=ContentFormat.MARKDOWN,
                            content=token.content.strip(),
                            order=len(elements),
                        )
                    )

        return elements

    def _parse_html(self, html_text: str, doc_id: str) -> list[ParsedElement]:
        parser = HTMLToElementsParser(doc_id)
        chunk_size = 65536
        for i in range(0, len(html_text), chunk_size):
            parser.feed(html_text[i : i + chunk_size])
        return parser.finish()

    def _assign_synthetic_pages(
        self,
        elements: list[ParsedElement],
        doc_id: str,
    ) -> tuple[list[ParsedPage], list[ParsedElement]]:
        pages: list[ParsedPage] = []
        page_no = 1
        page_id = f"{doc_id}_page_{page_no}"
        accumulated_chars = 0

        for el in elements:
            el_len = len(el.content)

            if accumulated_chars > 0 and accumulated_chars + el_len > self.max_page_chars:
                pages.append(ParsedPage(page_id=page_id, page_no=page_no))
                page_no += 1
                page_id = f"{doc_id}_page_{page_no}"
                accumulated_chars = 0

            el.page_id = page_id
            accumulated_chars += el_len

        if accumulated_chars > 0 or not pages:
            pages.append(ParsedPage(page_id=page_id, page_no=page_no))

        return pages, elements
