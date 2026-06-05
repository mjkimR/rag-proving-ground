from rag_core.chunkers.visual import visual_chunk_document
from rag_core.parsers.schemas import AssetRef, ContentFormat, ElementType, ParsedDocument, ParsedElement, ParsedPage


def test_visual_chunk_document_basic():
    # 1. Create a dummy ParsedDocument
    pages = [
        ParsedPage(
            page_id="p1",
            page_no=1,
            image=AssetRef(path="images/p1.jpg", mimetype="image/jpeg", width=1280.0, height=720.0, dpi=150),
            metadata={},
        ),
        ParsedPage(
            page_id="p2",
            page_no=2,
            image=AssetRef(path="images/p2.jpg", mimetype="image/jpeg", width=1280.0, height=720.0, dpi=150),
            metadata={},
        ),
        ParsedPage(
            page_id="p3",
            page_no=3,
            image=None,  # Should skip this page
            metadata={},
        ),
    ]

    elements = [
        ParsedElement(
            element_id="e1",
            page_id="p1",
            type=ElementType.PARAGRAPH,
            content="Hello Page 1",
            format=ContentFormat.TEXT,
            order=0,
        ),
        ParsedElement(
            element_id="e2",
            page_id="p2",
            type=ElementType.PARAGRAPH,
            content="Hello Page 2",
            format=ContentFormat.TEXT,
            order=0,
        ),
    ]

    doc = ParsedDocument(doc_id="d1", parser="docling", pages=pages, elements=elements)

    # 2. Call visual_chunk_document
    chunks = visual_chunk_document(doc)

    # 3. Asserts
    assert len(chunks) == 2
    assert chunks[0].chunk_id == "d1:vchunk:0000"
    assert chunks[0].page_content == "Hello Page 1"
    assert chunks[0].metadata["image_storage_path"] == "images/p1.jpg"
    assert chunks[0].metadata["page_number"] == 1

    assert chunks[1].chunk_id == "d1:vchunk:0001"
    assert chunks[1].page_content == "Hello Page 2"
    assert chunks[1].metadata["image_storage_path"] == "images/p2.jpg"
    assert chunks[1].metadata["page_number"] == 2
