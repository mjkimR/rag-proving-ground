from pathlib import Path
from typing import Any, ClassVar

from app_http_client import get_http_client

from rag_core.adapters.parser.interface import Parser, ParserInput
from rag_core.adapters.parser.providers.shared.fetcher import get_input_bytes
from rag_core.adapters.parser.providers.shared.type_conversion import process_parser_pages
from rag_core.config import get_fast_parser_settings
from rag_core.parsers.schemas import (
    PARSED_DOCUMENT_SCHEMA_VERSION,
    ParsedDocument,
)


class PyPdfium2Parser(Parser):
    """Client wrapper for fast-parser microservice running pypdfium2."""

    name: ClassVar[str] = "pypdfium2"
    schema_version: ClassVar[str] = PARSED_DOCUMENT_SCHEMA_VERSION

    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @classmethod
    def from_config(cls) -> "PyPdfium2Parser":
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

        pages_list = data.get("pages", [])
        pages, elements, full_text = process_parser_pages(pages_list, doc_id, parse_format="text")

        parsed_doc = ParsedDocument(
            doc_id=doc_id,
            source=parser_input.source,
            filename=parser_input.filename,
            mimetype=parser_input.content_type,
            parser=self.name,
            pages=pages,
            elements=elements,
            text=full_text,
            metadata={
                **parser_input.metadata,
            },
            raw=data,
        )

        return parsed_doc

    def from_cache_data(self, data: dict[str, Any]) -> ParsedDocument:
        """Restore parser result from cached JSON data."""
        return ParsedDocument.model_validate(data)
