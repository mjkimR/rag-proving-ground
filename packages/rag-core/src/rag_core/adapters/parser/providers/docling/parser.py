import base64
from typing import Any, ClassVar

from app_http_client import get_http_client

from rag_core.adapters.parser.interface import Parser, ParserInput
from rag_core.config import get_docling_parser_settings
from rag_core.parsers.schemas import PARSED_DOCUMENT_SCHEMA_VERSION, ParsedDocument

from .normalizer import normalize_docling_document


class DoclingParser(Parser):
    """Docling Serve parser provider."""

    name: ClassVar[str] = "docling"
    schema_version: ClassVar[str] = PARSED_DOCUMENT_SCHEMA_VERSION

    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @classmethod
    def from_config(cls) -> "DoclingParser":
        docling_settings = get_docling_parser_settings()
        return cls(
            base_url=str(docling_settings.base_url),
            timeout=docling_settings.timeout,
        )

    async def parse(self, parser_input: ParserInput) -> ParsedDocument:
        payload = self._build_payload(parser_input)
        client = get_http_client()
        response = await client.post(
            f"{self.base_url}/v1/convert/source",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()

        data = response.json()
        response_document = self._response_document(data)
        document_data = self._docling_document_data(response_document)

        markdown = self._extract_markdown(response_document) or ""
        text = self._extract_text(response_document) or ""
        html = self._extract_html(response_document) or ""
        return normalize_docling_document(
            document_data,
            parser_input=parser_input,
            parser_name=self.name,
            raw_response=data,
            markdown=markdown,
            text=text,
            html=html,
        )

    def from_cache_data(self, data: dict[str, Any]) -> ParsedDocument:
        """Restore Docling parser result from cached JSON data."""
        document = data.get("document")
        if isinstance(document, dict):
            return ParsedDocument.model_validate(document)
        return ParsedDocument.model_validate(data)

    def _response_document(self, data: dict[str, Any]) -> dict[str, Any]:
        document = data.get("document")
        if isinstance(document, dict):
            return document
        return data

    def _docling_document_data(self, document: dict[str, Any]) -> dict[str, Any]:
        json_content = document.get("json_content")
        if isinstance(json_content, dict):
            return json_content
        if self._looks_like_docling_document(document):
            return document
        raise ValueError(
            "Docling response does not include json_content. "
            'Request "json" in options.to_formats to build ParsedDocument.'
        )

    def _looks_like_docling_document(self, data: dict[str, Any]) -> bool:
        return {"name", "body", "texts", "pages"}.issubset(data)

    def _build_payload(self, parser_input: ParserInput) -> dict[str, Any]:
        if parser_input.source:
            return {
                "sources": [
                    {
                        "kind": "http",
                        "url": parser_input.source,
                    }
                ],
                "target": {"kind": "inbody"},
                "options": {
                    "to_formats": ["json", "html", "md", "text"],
                },
            }

        if parser_input.content is None:
            raise ValueError("Docling parser requires either source or content.")

        return {
            "sources": [
                {
                    "kind": "file",
                    "base64_string": base64.b64encode(parser_input.content).decode("ascii"),
                    "filename": parser_input.filename,
                    "mime_type": parser_input.content_type,
                }
            ],
            "target": {"kind": "inbody"},
            "options": {
                "to_formats": ["json"],
            },
        }

    def _extract_markdown(self, data: dict[str, Any]) -> str | None:
        document = self._first_document(data)
        for key in ("md_content", "markdown"):
            value = document.get(key)
            if isinstance(value, str):
                return value
        return None

    def _extract_text(self, data: dict[str, Any]) -> str | None:
        document = self._first_document(data)
        for key in ("text_content", "text"):
            value = document.get(key)
            if isinstance(value, str):
                return value
        return None

    def _extract_html(self, data: dict[str, Any]) -> str | None:
        document = self._first_document(data)
        for key in ("html_content", "html"):
            value = document.get(key)
            if isinstance(value, str):
                return value
        return None

    def _first_document(self, data: dict[str, Any]) -> dict[str, Any]:
        documents = data.get("documents")
        if isinstance(documents, list) and documents:
            document = documents[0]
            if isinstance(document, dict):
                return document
        return data
