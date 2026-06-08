import asyncio
import html.parser
import ipaddress
import re
import socket
import threading
from collections.abc import Iterable
from html import escape
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlparse

import httpcore
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


class HTMLToElementsParser(html.parser.HTMLParser):
    """HTML parser to convert HTML tags into ParsedElements."""

    BLOCK_TAGS: ClassVar[set[str]] = {
        "p",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "ul",
        "ol",
        "section",
        "blockquote",
        "pre",
        "code",
        "article",
        "aside",
        "footer",
        "header",
        "nav",
    }

    VOID_TAGS: ClassVar[set[str]] = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self, doc_id: str) -> None:
        super().__init__(convert_charrefs=True)
        self.doc_id = doc_id
        self.elements: list[ParsedElement] = []
        self.text_accumulator: list[str] = []
        self.current_tag_stack: list[str] = []

        # Ignore/blacklist tag state
        self.ignored_depth = 0
        self.ignored_tags = {"script", "style", "nav", "footer", "aside", "meta", "head"}

        # Table capture state
        self.in_table = False
        self.table_depth = 0
        self.table_html_accumulator: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()

        # Update ignored depth (only if not a void/self-closing tag)
        if tag_lower in self.ignored_tags and tag_lower not in self.VOID_TAGS:
            self.ignored_depth += 1

        # Reconstruct attributes string
        attr_str = ""
        if attrs:
            parts = []
            for name, val in attrs:
                if val is not None:
                    parts.append(f'{name}="{escape(val, quote=True)}"')
                else:
                    parts.append(name)
            attr_str = " " + " ".join(parts)

        # If inside a table, accumulate all tags directly
        if self.in_table:
            # We only track ignored tags inside tables in current_tag_stack
            if tag_lower in self.ignored_tags and tag_lower not in self.VOID_TAGS:
                self.current_tag_stack.append(tag_lower)
            self.table_html_accumulator.append(f"<{tag_lower}{attr_str}>")
            if tag_lower == "table":
                self.table_depth += 1
            return

        # Start of a table
        if tag_lower == "table":
            self._flush_text()
            if tag_lower not in self.VOID_TAGS:
                self.current_tag_stack.append(tag_lower)
            self.in_table = True
            self.table_depth = 1
            self.table_html_accumulator = [f"<table{attr_str}>"]
            return

        # Only push to stack if it's not a self-closing void tag
        if tag_lower not in self.VOID_TAGS:
            self.current_tag_stack.append(tag_lower)

        # Flush text when encountering block-level tags
        if tag_lower in self.BLOCK_TAGS:
            self._flush_text()

    def handle_data(self, data: str) -> None:
        if self.in_table:
            self.table_html_accumulator.append(escape(data))
        else:
            self.text_accumulator.append(data)

    def handle_comment(self, data: str) -> None:
        # HTML comments are explicitly ignored
        pass

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()

        if self.in_table:
            self.table_html_accumulator.append(f"</{tag_lower}>")
            if tag_lower == "table":
                self.table_depth -= 1
                if self.table_depth == 0:
                    table_html = "".join(self.table_html_accumulator)
                    ignored = self.ignored_depth > 0
                    self.elements.append(
                        ParsedElement(
                            element_id=f"{self.doc_id}_el_{len(self.elements)}",
                            type=ElementType.TABLE,
                            format=ContentFormat.HTML,
                            content=table_html,
                            order=len(self.elements),
                            ignored=ignored,
                        )
                    )
                    self.in_table = False
                    self.table_html_accumulator = []

        # Flush block tag close
        if not self.in_table and tag_lower in self.BLOCK_TAGS:
            self._flush_text()

        # Pop matching tag and any unclosed children from stack
        if tag_lower in self.current_tag_stack:
            while self.current_tag_stack:
                popped = self.current_tag_stack.pop()
                if popped in self.ignored_tags and popped not in self.VOID_TAGS:
                    self.ignored_depth = max(0, self.ignored_depth - 1)
                if popped == tag_lower:
                    break

    def _flush_text(self) -> None:
        text = "".join(self.text_accumulator).strip()
        self.text_accumulator = []
        if not text:
            return

        el_type = ElementType.PARAGRAPH
        level = None

        # Find the nearest active block tag
        nearest_block = None
        for tag in reversed(self.current_tag_stack):
            if tag in self.BLOCK_TAGS:
                nearest_block = tag
                break

        if nearest_block:
            if nearest_block in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                el_type = ElementType.HEADING
                level = int(nearest_block[1])
            elif nearest_block == "li":
                el_type = ElementType.LIST_ITEM
            elif nearest_block in {"ul", "ol"}:
                el_type = ElementType.LIST

        ignored = self.ignored_depth > 0

        self.elements.append(
            ParsedElement(
                element_id=f"{self.doc_id}_el_{len(self.elements)}",
                type=el_type,
                format=ContentFormat.TEXT,
                content=text,
                level=level,
                order=len(self.elements),
                ignored=ignored,
            )
        )

    def finish(self) -> list[ParsedElement]:
        self._flush_text()
        return self.elements


class SafeAsyncNetworkBackend(httpcore.AnyIOBackend):
    """Network backend that mitigates SSRF by resolving DNS and validating IP addresses before connecting."""

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        try:
            loop = asyncio.get_running_loop()
            addr_info = await loop.run_in_executor(
                None, socket.getaddrinfo, host, port, socket.AF_UNSPEC, socket.SOCK_STREAM
            )
        except Exception as exc:
            raise httpcore.ConnectError(f"DNS resolution failed for {host}: {exc}") from exc

        safe_ips = []
        for _family, _socktype, _proto, _canonname, sockaddr in addr_info:
            ip_str = sockaddr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
                if ip.is_private or ip.is_loopback or ip.is_link_local:
                    raise ValueError(f"SSRF Prevention: URL resolves to private/loopback/link-local IP: {ip_str}")
                safe_ips.append(ip_str)
            except ValueError as ve:
                raise httpcore.ConnectError(str(ve)) from ve

        if not safe_ips:
            raise httpcore.ConnectError(f"No safe IP addresses found for host {host}")

        # Connect directly to the resolved IP to prevent DNS rebinding attacks.
        # Note: Even though we pass the IP address as `host` to connect the TCP socket,
        # httpcore/httpx will still perform TLS/SSL handshake using the original hostname
        # (e.g. Server Name Indication/SNI and certificate validation) and keep the original
        # Host header from the request URL. This ensures SNI and certificate verification work correctly.
        target_ip = safe_ips[0]

        # Use type ignore since connect_tcp is dynamically typed on httpcore.AnyIOBackend
        return await super().connect_tcp(  # type: ignore
            host=target_ip,
            port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


_safe_http_client: httpx.AsyncClient | None = None
_safe_client_lock = threading.Lock()


def get_safe_http_client() -> httpx.AsyncClient:
    """Return a shared httpx.AsyncClient instance pre-configured with the SafeAsyncNetworkBackend."""
    global _safe_http_client
    if _safe_http_client is None:
        with _safe_client_lock:
            if _safe_http_client is None:
                try:
                    from app_http_client.config import get_http_client_settings

                    settings = get_http_client_settings()
                    limits = httpx.Limits(
                        max_connections=settings.max_connections,
                        max_keepalive_connections=settings.max_keepalive_connections,
                        keepalive_expiry=settings.keepalive_expiry,
                    )
                except Exception:
                    limits = httpx.Limits(max_connections=10, max_keepalive_connections=5, keepalive_expiry=5.0)

                transport = httpx.AsyncHTTPTransport(verify=True, limits=limits)
                transport._pool._network_backend = SafeAsyncNetworkBackend()  # type: ignore
                _safe_http_client = httpx.AsyncClient(transport=transport)
    return _safe_http_client


def _validate_ssrf(url: str) -> None:
    """Validate that the URL does not resolve to a private, loopback, or link-local address (SSRF mitigation)."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("Invalid URL: missing hostname")

        addr_info = socket.getaddrinfo(hostname, None)
        for _family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise ValueError(f"SSRF Prevention: URL resolves to private/loopback/link-local IP: {ip_str}")
    except ValueError as ve:
        raise ve
    except Exception as exc:
        raise ValueError(f"SSRF Validation failed during DNS resolution: {exc}") from exc


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
