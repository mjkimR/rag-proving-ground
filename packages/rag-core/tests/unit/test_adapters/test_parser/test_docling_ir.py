import hashlib
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from app_file_storage import FileStorageClient
from rag_core.adapters.parser.cache import ParserCache
from rag_core.adapters.parser.interface import ParserInput
from rag_core.adapters.parser.providers.docling.normalizer import normalize_docling_document
from rag_core.adapters.parser.providers.docling.parser import DoclingParser
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

    # Assert TableGridData is parsed correctly
    assert table.table_data is not None
    assert table.table_data.row_count == table.metadata["num_rows"]
    assert table.table_data.col_count == table.metadata["num_cols"]
    assert len(table.table_data.cells) > 0
    # Check individual cells
    first_cell = table.table_data.cells[0]
    assert first_cell.row_index is not None
    assert first_cell.col_index is not None
    assert first_cell.row_span >= 1
    assert first_cell.col_span >= 1
    assert first_cell.content is not None
    assert first_cell.cell_type in ("header", "data")
    assert first_cell.bbox is not None

    # Assert logical roles are populated
    headings = [el for el in parsed.elements if el.type == ElementType.HEADING]
    assert len(headings) > 0
    for h in headings:
        assert h.logical_role in ("title", "sectionHeading")

    # Assert tree hierarchy is built (some elements should have parent_id)
    child_elements = [el for el in parsed.elements if el.parent_id is not None]
    assert len(child_elements) > 0
    # Check that children_ids matches parent_ids
    for child in child_elements:
        parent = next(el for el in parsed.elements if el.element_id == child.parent_id)
        assert child.element_id in parent.children_ids


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


async def test_parser_cache_uses_parsing_config_hash_in_result_key() -> None:
    cache = ParserCache(_InMemoryStorage(), prefix="parser_cache")

    key = cache._result_key("abc", "hash123")

    assert key == "parser_cache/abc/hash123/parsed_data.json"


async def test_parser_cache_stores_original_file_and_meta_under_hash() -> None:
    storage = _InMemoryStorage()
    cache = ParserCache(storage, prefix="parser_cache")
    parser_input = ParserInput(
        content=b"example",
        filename="sample.pdf",
        content_type="application/pdf",
        metadata={"source": "unit"},
    )

    content_hash = await cache.store_file(parser_input, "hash123")

    assert content_hash == hashlib.sha256(b"example").hexdigest()
    assert not await storage.file_exists(f"parser_cache/{content_hash}/sample.pdf")
    meta = json.loads(await storage.download_file(f"parser_cache/{content_hash}/hash123/meta.json"))
    assert meta == {
        "content_type": "application/pdf",
        "hash_algorithm": "sha256",
        "extension": ".pdf",
        "filename": "sample.pdf",
        "content_hash": content_hash,
        "metadata": {"source": "unit"},
    }


def test_docling_parser_does_not_mix_generic_content_into_specific_formats() -> None:
    parser = DoclingParser("http://127.0.0.1")
    document = {"content": "<p>ambiguous</p>"}

    assert parser._extract_markdown(document) is None
    assert parser._extract_text(document) is None
    assert parser._extract_html(document) is None


async def test_parser_cache_update_meta_does_nested_merge() -> None:
    storage = _InMemoryStorage()
    cache = ParserCache(storage, prefix="parser_cache")
    parser_input = ParserInput(
        content=b"example",
        filename="sample.pdf",
        content_type="application/pdf",
    )
    content_hash = await cache.store_file(parser_input, "hash123")

    # 1. Update with first provider duration
    await cache._update_meta(content_hash, "hash123", {"parse_durations": {"docling": 1.23}})
    meta = json.loads(await storage.download_file(f"parser_cache/{content_hash}/hash123/meta.json"))
    assert meta["parse_durations"] == {"docling": 1.23}

    # 2. Update with second provider duration - should MERGE, not OVERWRITE
    await cache._update_meta(content_hash, "hash123", {"parse_durations": {"marker": 4.56}})
    meta = json.loads(await storage.download_file(f"parser_cache/{content_hash}/hash123/meta.json"))
    assert meta["parse_durations"] == {"docling": 1.23, "marker": 4.56}


def test_docling_normalizer_new_labels_and_warning_counts(mocker: Any) -> None:
    from rag_core.adapters.parser.providers.docling.normalizer import _UNSEEN_LABEL_WARNING_COUNTS

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


def test_docling_code_rendering() -> None:
    from rag_core.parsers.schemas import ContentFormat, ParsedDocument, ParsedPage

    doc = ParsedDocument(
        doc_id="test_doc",
        parser="docling",
        pages=[ParsedPage(page_id="p1", page_no=1)],
        elements=[
            ParsedElement(
                element_id="el1",
                type=ElementType.CODE,
                format=ContentFormat.TEXT,
                content="print('hello world')",
                order=0,
                ignored=False,
                page_id="p1",
            ),
        ],
    )

    markdown = doc.to_markdown()
    html = doc.to_html()

    assert markdown == "```\nprint('hello world')\n```"
    assert html == "<pre><code>print(&#x27;hello world&#x27;)</code></pre>"


def test_docling_normalizer_parent_child_hierarchy() -> None:
    from rag_core.chunkers.semantic import RAGSemanticChunker

    response_document = {
        "origin": {"filename": "sample.pdf", "mimetype": "application/pdf"},
        "pages": {"1": {"page_no": 1, "size": {"width": 612.0, "height": 792.0}}},
        "texts": [
            {"label": "list_item", "text": "Item 1", "marker": "-", "parent": {"$ref": "#/groups/0"}},
            {"label": "list_item", "text": "Item 2", "marker": "-", "parent": {"$ref": "#/groups/0"}},
            {"label": "paragraph", "text": "OCR Text inside image", "parent": {"$ref": "#/pictures/0"}},
        ],
        "pictures": [
            {
                "label": "picture",
                "image": {"uri": "data:image/png;base64,123", "size": {"width": 100, "height": 100}},
                "children": [{"$ref": "#/texts/2"}],
            }
        ],
        "tables": [],
        "groups": [
            {
                "label": "list",
                "children": [{"$ref": "#/texts/0"}, {"$ref": "#/texts/1"}],
            }
        ],
        "body": {
            "children": [
                {"$ref": "#/groups/0"},
                {"$ref": "#/pictures/0"},
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

    # We expect 5 elements:
    # 1. LIST parent (#/groups/0)
    # 2. LIST_ITEM 1 (#/texts/0)
    # 3. LIST_ITEM 2 (#/texts/1)
    # 4. IMAGE parent (#/pictures/0)
    # 5. PARAGRAPH (#/texts/2)
    assert len(parsed.elements) == 5

    group_el = next(el for el in parsed.elements if el.element_id == "#/groups/0")
    assert group_el.type == ElementType.LIST
    assert group_el.content == ""
    assert group_el.children_ids == ["#/texts/0", "#/texts/1"]

    item1_el = next(el for el in parsed.elements if el.element_id == "#/texts/0")
    assert item1_el.type == ElementType.LIST_ITEM
    assert item1_el.content == "- Item 1"
    assert item1_el.parent_id == "#/groups/0"

    item2_el = next(el for el in parsed.elements if el.element_id == "#/texts/1")
    assert item2_el.type == ElementType.LIST_ITEM
    assert item2_el.content == "- Item 2"
    assert item2_el.parent_id == "#/groups/0"

    picture_el = next(el for el in parsed.elements if el.element_id == "#/pictures/0")
    assert picture_el.type == ElementType.IMAGE
    assert picture_el.children_ids == ["#/texts/2"]

    ocr_el = next(el for el in parsed.elements if el.element_id == "#/texts/2")
    assert ocr_el.type == ElementType.PARAGRAPH
    assert ocr_el.content == "OCR Text inside image"
    assert ocr_el.parent_id == "#/pictures/0"

    # Verify semantic chunking does not duplicate list contents or skip image OCR texts
    chunker = RAGSemanticChunker()
    chunks = chunker.chunk_document(parsed)

    # 3 chunks should exist: list items (merged), picture markdown, and OCR text
    assert len(chunks) == 3
    assert "- Item 1\n- Item 2" in chunks[0].page_content
    assert "![" in chunks[1].page_content
    assert "OCR Text inside image" in chunks[2].page_content


def test_docling_normalizer_new_mapped_labels() -> None:
    response_document = {
        "origin": {"filename": "sample.pdf", "mimetype": "application/pdf"},
        "pages": {"1": {"page_no": 1, "size": {"width": 612.0, "height": 792.0}}},
        "texts": [
            {"label": "reference", "text": "Smith et al., 2020"},
            {"label": "form", "text": "Name: John Doe"},
            {"label": "key_value_region", "text": "Age: 30"},
            {"label": "checkbox_selected", "text": "Opt-in"},
            {"label": "checkbox-unselected", "text": "Opt-out"},
        ],
        "pictures": [
            {
                "label": "chart",
                "image": {"uri": "data:image/png;base64,chart_data", "size": {"width": 200, "height": 150}},
                "children": [],
            }
        ],
        "tables": [],
        "groups": [],
        "body": {
            "children": [
                {"$ref": "#/texts/0"},
                {"$ref": "#/texts/1"},
                {"$ref": "#/texts/2"},
                {"$ref": "#/texts/3"},
                {"$ref": "#/texts/4"},
                {"$ref": "#/pictures/0"},
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

    assert len(parsed.elements) == 6

    assert parsed.elements[0].type == ElementType.PARAGRAPH
    assert parsed.elements[0].content == "Smith et al., 2020"

    assert parsed.elements[1].type == ElementType.PARAGRAPH
    assert parsed.elements[1].content == "Name: John Doe"

    assert parsed.elements[2].type == ElementType.PARAGRAPH
    assert parsed.elements[2].content == "Age: 30"

    assert parsed.elements[3].type == ElementType.PARAGRAPH
    assert parsed.elements[3].content == "[x] Opt-in"

    assert parsed.elements[4].type == ElementType.PARAGRAPH
    assert parsed.elements[4].content == "[ ] Opt-out"

    assert parsed.elements[5].type == ElementType.IMAGE
    assert parsed.elements[5].asset is not None
    assert parsed.elements[5].asset.uri == "data:image/png;base64,chart_data"
