import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from app_file_storage import FileStorageClient
from rag_core.adapters.parser.cache import ParserCache
from rag_core.adapters.parser.interface import ParserInput
from rag_core.adapters.parser.normalizers import normalize_docling_document
from rag_core.adapters.parser.providers.docling import DoclingParser
from rag_core.parsers.schemas import ElementType, ParsedDocument


class _InMemoryStorage(FileStorageClient):
    """Simple in-memory FileStorageClient for unit tests."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    @classmethod
    async def from_env(cls) -> "_InMemoryStorage":
        return cls()

    async def close(self) -> None:
        pass

    async def upload_file(self, file_path: str, data: bytes) -> None:
        self._store[file_path] = data

    async def download_file(self, file_path: str) -> bytes:
        if file_path not in self._store:
            raise FileNotFoundError(file_path)
        return self._store[file_path]

    async def download_file_stream(self, file_path: str) -> AsyncIterator[bytes]:
        yield await self.download_file(file_path)

    async def delete_file(self, file_path: str) -> None:
        self._store.pop(file_path, None)

    async def list_files(self, prefix: str) -> AsyncIterator[str]:
        for key in list(self._store):
            if key.startswith(prefix):
                yield key

    async def file_exists(self, file_path: str) -> bool:
        return file_path in self._store

    async def get_file_metadata(self, file_path: str) -> dict[str, Any]:
        if file_path not in self._store:
            raise FileNotFoundError(file_path)
        return {"size": len(self._store[file_path]), "path": file_path}


EXAMPLE_PATH = Path(__file__).parent / "example" / "docling.json"


def test_docling_normalizer_builds_parsed_document() -> None:
    payload = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    response_document = payload["data"]["document"]

    parsed = normalize_docling_document(
        response_document["json_content"],
        parser_input=ParserInput(filename="sample.pdf", content_type="application/pdf"),
        parser_name="docling",
        raw_response=payload["data"],
        markdown=payload["markdown"],
        text=payload["text"],
        html="<html></html>",
    )

    assert parsed.schema_version == "1.0"
    assert parsed.parser == "docling"
    assert parsed.html == "<html></html>"
    assert len(parsed.pages) == 1
    assert parsed.elements[0].type == ElementType.HEADING
    assert parsed.elements[0].page_id == parsed.pages[0].page_id

    table = next(element for element in parsed.elements if element.type == ElementType.TABLE)
    assert table.format == "html"
    assert table.content.startswith("<table>")
    assert table.metadata["is_complex"] is True


def test_docling_cache_round_trip_restores_parsed_document() -> None:
    payload = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    response_document = payload["data"]["document"]
    parser = DoclingParser("http://127.0.0.1")
    parsed = normalize_docling_document(
        response_document["json_content"],
        parser_input=ParserInput(filename="sample.pdf", content_type="application/pdf"),
        parser_name=parser.name,
        raw_response=payload["data"],
        markdown=payload["markdown"],
        text=payload["text"],
    )

    cache_data = parser.to_cache_data(parsed)
    restored = parser.from_cache_data(cache_data)

    assert isinstance(restored, ParsedDocument)
    assert restored.schema_version == "1.0"


@pytest.mark.asyncio
async def test_parser_cache_uses_schema_version_in_result_key() -> None:
    cache = ParserCache(_InMemoryStorage(), prefix="parser_cache")

    key = cache._result_key("abc", "docling", schema_version="1.0")

    assert key == "parser_cache/abc/docling-1.0.json"


@pytest.mark.asyncio
async def test_parser_cache_stores_original_file_and_meta_under_hash() -> None:
    storage = _InMemoryStorage()
    cache = ParserCache(storage, prefix="parser_cache")
    parser_input = ParserInput(
        content=b"example",
        filename="sample.pdf",
        content_type="application/pdf",
        metadata={"source": "unit"},
    )

    md5_hash = await cache.store_file(parser_input)

    assert not await storage.file_exists(f"parser_cache/{md5_hash}/sample.pdf")
    meta = json.loads(await storage.download_file(f"parser_cache/{md5_hash}/meta.json"))
    assert meta == {
        "content_type": "application/pdf",
        "extension": ".pdf",
        "filename": "sample.pdf",
        "md5_hash": md5_hash,
        "metadata": {"source": "unit"},
    }


def test_docling_parser_does_not_mix_generic_content_into_specific_formats() -> None:
    parser = DoclingParser("http://127.0.0.1")
    document = {"content": "<p>ambiguous</p>"}

    assert parser._extract_markdown(document) is None
    assert parser._extract_text(document) is None
    assert parser._extract_html(document) is None
