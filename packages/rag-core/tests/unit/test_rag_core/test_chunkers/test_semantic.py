from rag_core.chunkers import ChunkedDocument, ChunkingConfig, chunk_document
from rag_core.parsers import (
    AssetRef,
    BoundingBox,
    ContentFormat,
    ElementType,
    ParsedDocument,
    ParsedElement,
    ParsedPage,
)
from rag_core.tokenizers import BaseTokenizer


def test_chunk_document_enriches_content_with_heading_breadcrumb() -> None:
    document = ParsedDocument(
        doc_id="doc",
        parser="unit",
        elements=[
            ParsedElement(
                element_id="h1",
                type=ElementType.HEADING,
                format=ContentFormat.TEXT,
                content="취업규칙",
                level=1,
                order=1,
            ),
            ParsedElement(
                element_id="h2",
                type=ElementType.HEADING,
                format=ContentFormat.TEXT,
                content="휴일 및 휴가",
                level=2,
                order=2,
            ),
            ParsedElement(
                element_id="p1",
                type=ElementType.PARAGRAPH,
                format=ContentFormat.TEXT,
                content="연차휴가는 근로기준법에 따른다.",
                page_id="page-1",
                order=3,
            ),
        ],
    )

    chunks = chunk_document(document)

    assert len(chunks) == 1
    assert chunks[0].page_content == "취업규칙 > 휴일 및 휴가: 연차휴가는 근로기준법에 따른다."
    assert chunks[0].source_element_ids == ["p1"]
    assert chunks[0].page_ids == ["page-1"]
    assert chunks[0].metadata["breadcrumb"] == ["취업규칙", "휴일 및 휴가"]


def test_chunk_document_merges_short_sibling_list_items() -> None:
    document = ParsedDocument(
        doc_id="doc",
        parser="unit",
        elements=[
            ParsedElement(
                element_id="h1",
                type=ElementType.HEADING,
                format=ContentFormat.TEXT,
                content="보안 규정",
                level=1,
                order=1,
            ),
            ParsedElement(
                element_id="li1",
                type=ElementType.LIST_ITEM,
                format=ContentFormat.MARKDOWN,
                content="- 비밀번호는 90일마다 변경한다.",
                level=1,
                order=2,
            ),
            ParsedElement(
                element_id="li2",
                type=ElementType.LIST_ITEM,
                format=ContentFormat.MARKDOWN,
                content="- 외부 공유를 금지한다.",
                level=1,
                order=3,
            ),
        ],
    )

    chunks = chunk_document(document, ChunkingConfig(merge_max_chars=120))

    assert len(chunks) == 1
    assert chunks[0].page_content == "보안 규정: - 비밀번호는 90일마다 변경한다.\n- 외부 공유를 금지한다."
    assert chunks[0].source_element_ids == ["li1", "li2"]
    assert chunks[0].metadata["element_type"] == "merged"


def test_chunk_document_renders_image_asset_as_markdown() -> None:
    document = ParsedDocument(
        doc_id="doc",
        parser="unit",
        elements=[
            ParsedElement(
                element_id="img1",
                type=ElementType.IMAGE,
                format=ContentFormat.ASSET_REF,
                content="차트",
                asset=AssetRef(uri="s3://bucket/chart.png"),
                order=1,
            )
        ],
    )

    chunks = chunk_document(document)

    assert chunks[0].page_content == "![차트](s3://bucket/chart.png)"


def test_chunk_document_adds_retrieval_metadata() -> None:
    document = ParsedDocument(
        doc_id="doc",
        parser="unit",
        pages=[
            ParsedPage(page_id="page-1", page_no=1),
            ParsedPage(page_id="page-2", page_no=2),
        ],
        elements=[
            ParsedElement(
                element_id="p1",
                type=ElementType.PARAGRAPH,
                format=ContentFormat.TEXT,
                content="첫 페이지 첫 문단",
                page_id="page-1",
                order=1,
                bbox=BoundingBox(left=1, top=2, right=3, bottom=4, coord_origin="TOPLEFT"),
            ),
            ParsedElement(
                element_id="p2",
                type=ElementType.PARAGRAPH,
                format=ContentFormat.TEXT,
                content="첫 페이지 마지막 문단",
                page_id="page-1",
                order=2,
            ),
            ParsedElement(
                element_id="p3",
                type=ElementType.PARAGRAPH,
                format=ContentFormat.TEXT,
                content="둘째 페이지 문단",
                page_id="page-2",
                order=3,
            ),
        ],
    )

    chunks = chunk_document(document)

    assert chunks[0].metadata["source_element_orders"] == [1]
    assert chunks[0].metadata["source_element_types"] == ["paragraph"]
    assert chunks[0].metadata["element_order_start"] == 1
    assert chunks[0].metadata["element_order_end"] == 1
    assert chunks[0].metadata["page_numbers"] == [1]
    assert chunks[0].metadata["source_bboxes"] == [
        {
            "left": 1.0,
            "top": 2.0,
            "right": 3.0,
            "bottom": 4.0,
            "coord_origin": "TOPLEFT",
        }
    ]
    assert chunks[0].metadata["previous_chunk_id"] is None
    assert chunks[0].metadata["next_chunk_id"] == chunks[1].chunk_id
    assert chunks[0].metadata["is_first_chunk_on_page"] is True
    assert chunks[0].metadata["is_last_chunk_on_page"] is False
    assert chunks[1].metadata["is_first_chunk_on_page"] is False
    assert chunks[1].metadata["is_last_chunk_on_page"] is True
    assert chunks[2].metadata["is_first_chunk_on_page"] is True
    assert chunks[2].metadata["is_last_chunk_on_page"] is True


def test_chunk_document_marks_fallback_split_parts() -> None:
    document = ParsedDocument(
        doc_id="doc",
        parser="unit",
        pages=[ParsedPage(page_id="page-1", page_no=1)],
        elements=[
            ParsedElement(
                element_id="p1",
                type=ElementType.PARAGRAPH,
                format=ContentFormat.TEXT,
                content="첫 문장입니다. 둘째 문장입니다. 셋째 문장입니다. 넷째 문장입니다.",
                page_id="page-1",
                order=1,
            ),
        ],
    )

    chunks = chunk_document(document, ChunkingConfig(chunk_size=20, chunk_overlap=0))

    assert len(chunks) > 1
    assert [chunk.metadata["chunk_part_index"] for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.metadata["chunk_part_count"] == len(chunks) for chunk in chunks)
    assert all(chunk.metadata["is_split_chunk"] is True for chunk in chunks)
    assert chunks[0].metadata["previous_chunk_id"] is None
    assert chunks[-1].metadata["next_chunk_id"] is None
    assert chunks[0].metadata["is_first_chunk_on_page"] is True
    assert chunks[-1].metadata["is_last_chunk_on_page"] is True


def test_chunked_document_converts_to_langchain_document() -> None:
    chunk = ChunkedDocument(
        chunk_id="doc:chunk:0001",
        doc_id="doc",
        page_content="본문",
        order=1,
        source_element_ids=["p1"],
        page_ids=["page-1"],
        metadata={"filename": "sample.pdf", "chunk_id": "stale"},
    )

    document = chunk.to_langchain_document()

    assert document.page_content == "본문"
    assert document.metadata == {
        "filename": "sample.pdf",
        "chunk_id": "doc:chunk:0001",
        "doc_id": "doc",
        "order": 1,
        "source_element_ids": ["p1"],
        "page_ids": ["page-1"],
    }


class MockTokenizer(BaseTokenizer):
    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 5)

    def encode(self, text: str) -> list[int]:
        return [ord(c) for c in text]

    def decode(self, tokens: list[int]) -> str:
        return "".join(chr(t) for t in tokens)

    def truncate(self, text: str, max_tokens: int) -> str:
        return text[: max_tokens * 5]


def test_chunk_document_with_tokenizer_splits_by_tokens() -> None:
    tokenizer = MockTokenizer()
    document = ParsedDocument(
        doc_id="doc",
        parser="unit",
        elements=[
            ParsedElement(
                element_id="p1",
                type=ElementType.PARAGRAPH,
                format=ContentFormat.TEXT,
                content="A" * 60,
                page_id="page-1",
                order=1,
            )
        ],
    )

    # chunk_size is 10 tokens (50 chars). A*60 is 12 tokens, which exceeds 10, so it should split.
    chunks = chunk_document(document, ChunkingConfig(chunk_size=10, chunk_overlap=2), tokenizer=tokenizer)
    assert len(chunks) > 1

    # chunk_size is 15 tokens (75 chars). A*60 is 12 tokens, which is under 15, so it should NOT split.
    chunks_no_split = chunk_document(document, ChunkingConfig(chunk_size=15, chunk_overlap=2), tokenizer=tokenizer)
    assert len(chunks_no_split) == 1
    assert chunks_no_split[0].page_content == "A" * 60


def test_chunk_document_truncates_summary_by_tokens() -> None:
    tokenizer = MockTokenizer()
    document = ParsedDocument(
        doc_id="doc",
        parser="unit",
        elements=[
            ParsedElement(
                element_id="p1",
                type=ElementType.PARAGRAPH,
                format=ContentFormat.TEXT,
                content="Short text",
                page_id="page-1",
                order=1,
            )
        ],
    )
    # chunk_size = 20 tokens. max_summary_tokens is 20 * 0.5 = 10 tokens.
    # summary "B" * 80 is 16 tokens, which gets truncated to (10 - 1) = 9 tokens (45 characters) + "...".
    summary = "B" * 80
    chunks = chunk_document(
        document,
        ChunkingConfig(chunk_size=20, chunk_overlap=0),
        summary=summary,
        tokenizer=tokenizer,
    )
    assert len(chunks) == 1
    expected_summary = "B" * 45 + "..."
    assert chunks[0].page_content.startswith(f"[Document Summary: {expected_summary}]")
