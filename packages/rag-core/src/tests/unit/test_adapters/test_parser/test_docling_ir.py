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
from rag_core.parsers.schemas import ElementType, ParsedDocument, ParsedElement


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


@pytest.mark.asyncio
async def test_parser_cache_update_meta_does_nested_merge() -> None:
    storage = _InMemoryStorage()
    cache = ParserCache(storage, prefix="parser_cache")
    parser_input = ParserInput(
        content=b"example",
        filename="sample.pdf",
        content_type="application/pdf",
    )
    md5_hash = await cache.store_file(parser_input)

    # 1. Update with first provider duration
    await cache._update_meta(md5_hash, {"parse_durations": {"docling": 1.23}})
    meta = json.loads(await storage.download_file(f"parser_cache/{md5_hash}/meta.json"))
    assert meta["parse_durations"] == {"docling": 1.23}

    # 2. Update with second provider duration - should MERGE, not OVERWRITE
    await cache._update_meta(md5_hash, {"parse_durations": {"marker": 4.56}})
    meta = json.loads(await storage.download_file(f"parser_cache/{md5_hash}/meta.json"))
    assert meta["parse_durations"] == {"docling": 1.23, "marker": 4.56}


def test_docling_normalizer_new_labels_and_warning_counts(mocker: Any) -> None:
    from rag_core.adapters.parser.normalizers.docling import _UNSEEN_LABEL_WARNING_COUNTS

    # Reset warning counts to get a clean test state
    _UNSEEN_LABEL_WARNING_COUNTS.clear()

    # Mock loguru warning
    from loguru import logger

    mock_warning = mocker.patch.object(logger, "warning")

    # Create mock response document
    response_document = {
        "origin": {"filename": "sample.pdf", "mimetype": "application/pdf"},
        "pages": {"1": {"page_no": 1, "size": {"width": 612.0, "height": 792.0}}},
        "texts": [
            {"label": "footnote", "text": "This is a footnote text."},
            {"label": "caption", "text": "Figure 1: Captioned text."},
            {"label": "formula", "text": "E = mc^2"},
            {"label": "page_header", "text": "Header Page 1"},
            {"label": "page_footer", "text": "Footer Page 1"},
            {"label": "document_index", "text": "TOC"},
            {"label": "new_mysterious_label", "text": "Some mystery element."},
        ],
        "pictures": [],
        "tables": [],
        "groups": [],
        "body": {
            "children": [
                {"$ref": "#/texts/0"},
                {"$ref": "#/texts/1"},
                {"$ref": "#/texts/2"},
                {"$ref": "#/texts/3"},
                {"$ref": "#/texts/4"},
                {"$ref": "#/texts/5"},
                {"$ref": "#/texts/6"},
            ]
        },
    }

    parsed = normalize_docling_document(
        response_document,
        parser_input=ParserInput(filename="sample.pdf", content_type="application/pdf"),
        parser_name="docling",
        raw_response={},
        markdown="",
        text="",
    )

    # Assert footnotes, captions, and formulas map to correct semantic types
    assert parsed.elements[0].type == ElementType.FOOTNOTE
    assert parsed.elements[0].content == "This is a footnote text."
    assert parsed.elements[0].ignored is False

    assert parsed.elements[1].type == ElementType.CAPTION
    assert parsed.elements[1].content == "Figure 1: Captioned text."
    assert parsed.elements[1].ignored is False

    assert parsed.elements[2].type == ElementType.EQUATION
    assert parsed.elements[2].content == "E = mc^2"
    assert parsed.elements[2].ignored is False

    # Assert layout elements map correctly and are flagged as ignored
    assert parsed.elements[3].type == ElementType.PAGE_HEADER
    assert parsed.elements[3].content == "Header Page 1"
    assert parsed.elements[3].ignored is True

    assert parsed.elements[4].type == ElementType.PAGE_FOOTER
    assert parsed.elements[4].content == "Footer Page 1"
    assert parsed.elements[4].ignored is True

    assert parsed.elements[5].type == ElementType.SECTION_INDEX
    assert parsed.elements[5].content == "<table>\n\n</table>"
    assert parsed.elements[5].ignored is True

    # Assert unknown label behavior
    assert parsed.elements[6].type == ElementType.UNKNOWN
    assert parsed.elements[6].content == "Some mystery element."
    assert parsed.elements[6].ignored is False

    # Assert that a warning was logged for the unseen label
    mock_warning.assert_called_once()
    assert "new_mysterious_label" in mock_warning.call_args[0][0]

    # Verify warning limit of 3 works
    mock_warning.reset_mock()
    for _ in range(5):
        normalize_docling_document(
            {**response_document, "body": {"children": [{"$ref": "#/texts/6"}]}},
            parser_input=ParserInput(filename="sample.pdf", content_type="application/pdf"),
            parser_name="docling",
            raw_response={},
            markdown="",
            text="",
        )
    # It was already called once, so it should only be called 2 more times to hit limit of 3
    assert mock_warning.call_count == 2


def test_semantic_chunker_ignores_layout_boilerplate() -> None:
    from rag_core.chunkers.semantic import RAGSemanticChunker
    from rag_core.parsers.schemas import ContentFormat, ParsedDocument, ParsedPage

    doc = ParsedDocument(
        doc_id="test_doc",
        parser="docling",
        pages=[ParsedPage(page_id="p1", page_no=1)],
        elements=[
            ParsedElement(
                element_id="el1",
                type=ElementType.PAGE_HEADER,
                format=ContentFormat.MARKDOWN,
                content="Layout Header Text",
                order=0,
                ignored=True,
                page_id="p1",
            ),
            ParsedElement(
                element_id="el2",
                type=ElementType.PARAGRAPH,
                format=ContentFormat.MARKDOWN,
                content="Actual content paragraph.",
                order=1,
                ignored=False,
                page_id="p1",
            ),
        ],
    )

    chunker = RAGSemanticChunker()
    chunks = chunker.chunk_document(doc)

    # Assert layout header is bypassed, only actual paragraph is chunked
    assert len(chunks) == 1
    assert "Layout Header Text" not in chunks[0].page_content
    assert "Actual content paragraph." in chunks[0].page_content
