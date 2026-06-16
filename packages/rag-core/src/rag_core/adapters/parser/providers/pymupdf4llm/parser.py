from pathlib import Path
from typing import Any, ClassVar

from app_http_client import get_http_client

from rag_core.adapters.parser.interface import Parser, ParserInput
from rag_core.adapters.parser.providers.native_text.parser import NativeTextParser
from rag_core.adapters.parser.providers.shared.fetcher import get_input_bytes
from rag_core.config import get_fast_parser_settings
from rag_core.parsers.schemas import (
    PARSED_DOCUMENT_SCHEMA_VERSION,
    ParsedDocument,
    ParsedElement,
    ParsedPage,
)


class PyMuPDF4LLMParser(Parser):
    """Client wrapper for fast-parser microservice running pymupdf4llm."""

    name: ClassVar[str] = "pymupdf4llm"
    schema_version: ClassVar[str] = PARSED_DOCUMENT_SCHEMA_VERSION

    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @classmethod
    def from_config(cls) -> "PyMuPDF4LLMParser":
        settings = get_fast_parser_settings()
        return cls(base_url=settings.base_url, timeout=settings.timeout)

    async def parse(self, parser_input: ParserInput) -> ParsedDocument:
        # Determine document ID
        doc_id = parser_input.metadata.get("doc_id")
        if not doc_id:
            source = parser_input.source or parser_input.filename or "document"
            doc_id = Path(source).stem or source

        content_bytes = await get_input_bytes(parser_input)

        client = get_http_client()
        files = {
            "file": (
                parser_input.filename or "document.pdf",
                content_bytes,
                parser_input.content_type or "application/pdf",
            )
        }

        response = await client.post(
            f"{self.base_url}/{self.name}/parse",
            files=files,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        # Parse and normalize response
        pages_list = data.get("pages", [])
        markdown_text = data.get("markdown", "")

        pages: list[ParsedPage] = []
        elements: list[ParsedElement] = []

        native_text_parser = NativeTextParser()

        # Loop through pages to generate elements per page
        for page_data in pages_list:
            page_no = page_data.get("page_no", 1)
            page_text = page_data.get("text", "")
            page_id = f"{doc_id}_page_{page_no}"

            pages.append(ParsedPage(page_id=page_id, page_no=page_no))

            # Parse page markdown content into elements
            page_elements = native_text_parser._parse_markdown(page_text, doc_id)
            for el in page_elements:
                # Assign actual page_id and page_no to each element
                el.page_id = page_id
                elements.append(el)

        # Fix sequence/order of elements and ensure element IDs are unique
        for idx, el in enumerate(elements):
            el.order = idx
            el.element_id = f"{doc_id}_el_{idx}"

        parsed_doc = ParsedDocument(
            doc_id=doc_id,
            source=parser_input.source,
            filename=parser_input.filename,
            mimetype=parser_input.content_type,
            parser=self.name,
            pages=pages,
            elements=elements,
            markdown=markdown_text,
            text=markdown_text,
            metadata={
                **parser_input.metadata,
            },
            raw=data,
        )

        return parsed_doc

    def from_cache_data(self, data: dict[str, Any]) -> ParsedDocument:
        """Restore parser result from cached JSON data."""
        return ParsedDocument.model_validate(data)
