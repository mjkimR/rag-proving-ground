from pathlib import Path

import pytest
from rag_core.parsers.schemas import ElementType, ParsedDocument


def test_no_unknown_elements(docling_dataset_document: ParsedDocument) -> None:
    """Verify that no parsed elements have ElementType.UNKNOWN semantic type."""
    for element in docling_dataset_document.elements:
        assert element.type != ElementType.UNKNOWN, (
            f"Element {element.element_id} in {docling_dataset_document.filename} "
            f"has UNKNOWN type: content='{element.content}'"
        )


def test_element_counts_and_type_integrity(docling_dataset_document: ParsedDocument) -> None:
    """Verify that the normalized ParsedDocument elements preserve the raw source elements counts."""
    raw = docling_dataset_document.raw
    if not raw or "document" not in raw or "json_content" not in raw["document"]:
        pytest.skip("Raw docling json_content is missing in docling_dataset_document")

    json_content = raw["document"]["json_content"]

    # 1. Verify text elements count matches (ignoring table-associated texts that are skipped by normalizer)
    raw_texts = json_content.get("texts", [])
    expected_texts_count = len(
        [
            t
            for t in raw_texts
            if not (isinstance(t.get("parent"), dict) and t["parent"].get("$ref", "").startswith("#/tables/"))
        ]
    )
    parsed_texts = [
        el
        for el in docling_dataset_document.elements
        if el.type
        in (
            ElementType.HEADING,
            ElementType.PARAGRAPH,
            ElementType.LIST_ITEM,
            ElementType.PAGE_HEADER,
            ElementType.PAGE_FOOTER,
            ElementType.FOOTNOTE,
            ElementType.CAPTION,
            ElementType.EQUATION,
        )
    ]
    assert len(parsed_texts) == expected_texts_count, (
        f"Text elements count mismatch in {docling_dataset_document.filename}: "
        f"expected {expected_texts_count}, got {len(parsed_texts)}"
    )

    # 2. Verify picture elements count matches
    raw_pictures_count = len(json_content.get("pictures", []))
    parsed_pictures = [el for el in docling_dataset_document.elements if el.type == ElementType.IMAGE]
    assert len(parsed_pictures) == raw_pictures_count, (
        f"Image elements count mismatch in {docling_dataset_document.filename}: "
        f"expected {raw_pictures_count}, got {len(parsed_pictures)}"
    )

    # 3. Verify table elements count matches
    raw_tables_count = len(json_content.get("tables", []))
    parsed_tables = [el for el in docling_dataset_document.elements if el.type == ElementType.TABLE]
    assert len(parsed_tables) == raw_tables_count, (
        f"Table elements count mismatch in {docling_dataset_document.filename}: "
        f"expected {raw_tables_count}, got {len(parsed_tables)}"
    )


CRITICAL_SNIPPETS = {
    "076523s007lbl_p2": [
        "your liver",
        "Use protective clothin",
        "insect repellents, and bednets",
    ],
    "1212.1661v1_page7": [
        "August",
        "ORPR",
        "112.917",
        "2.914",
    ],
    "1634690602_page10": [
        "Product (active substance(s))",
        "CVMP meeting date",
        "Recommendation - SPC change",
    ],
    "1653739079_page34": [
        "jspears on DSK121TN23PROD",
        "Implicit Price Deflator",
        "Rules and Regulations",
    ],
    "2010-k_page85": [
        "Management's Discussion and Analysis",
        "tax credit investments",
        "Other investments include",
    ],
    "2501.17887v1_p1-2": [
        "Docling: An Efficient Open-Source Toolkit",
        "Nikolaos Livathinos",
        "Document Conversion",
    ],
    "2501.17887v1_p4-5": [
        "Layout",
        "Tables",
        "Docling",
        "Easy",
    ],
    "AONR32314_page1": [
        "ALPHA&OMEGA",
        "Low R DS(ON)",
        "RoHS and Halogen-Free Compliant",
    ],
    "DS5795A-06_page2": [
        "Functional Pin Description",
        "EN",
        "Pin Function",
    ],
}


def test_text_completeness(docling_dataset_document: ParsedDocument) -> None:
    """Verify that critical text snippets are fully preserved after parsing and rendering."""
    filename = docling_dataset_document.filename or ""
    stem = Path(filename).stem
    if not stem or stem not in CRITICAL_SNIPPETS:
        pytest.skip(f"No critical snippets mapped for stem: {stem}")

    # Use include_ignored=True to ensure boilerplate page headers like "Rules and Regulations" are searched
    full_markdown = docling_dataset_document.to_markdown(include_ignored=True)
    # Normalize whitespaces to prevent double-space format discrepancies from causing failures
    normalized_markdown = " ".join(full_markdown.split())

    for snippet in CRITICAL_SNIPPETS[stem]:
        assert snippet in normalized_markdown, (
            f"Text completeness validation failed in {filename}: missing critical snippet '{snippet}'"
        )


def test_docling_table_grid_data(docling_dataset_document: ParsedDocument) -> None:
    """Verify that tables in the normalized document have valid grid and cell structures."""
    tables = [el for el in docling_dataset_document.elements if el.type == ElementType.TABLE]
    for table in tables:
        assert table.format == "html"
        assert table.content.startswith("<table>")
        assert table.table_data is not None
        assert table.table_data.row_count == table.metadata.get("num_rows")
        assert table.table_data.col_count == table.metadata.get("num_cols")
        assert len(table.table_data.cells) > 0
        for cell in table.table_data.cells:
            assert cell.row_index is not None
            assert cell.col_index is not None
            assert cell.row_span >= 1
            assert cell.col_span >= 1
            assert cell.cell_type in ("header", "data")


def test_docling_logical_roles(docling_dataset_document: ParsedDocument) -> None:
    """Verify that logical roles like title and sectionHeading are mapped correctly for headings."""
    headings = [el for el in docling_dataset_document.elements if el.type == ElementType.HEADING]
    for h in headings:
        assert h.logical_role in ("title", "sectionHeading", None)


def test_docling_hierarchy(docling_dataset_document: ParsedDocument) -> None:
    """Verify that parent_id references in child elements are consistent with children_ids in parent elements."""
    child_elements = [el for el in docling_dataset_document.elements if el.parent_id is not None]
    for child in child_elements:
        parent = next(el for el in docling_dataset_document.elements if el.element_id == child.parent_id)
        assert child.element_id in parent.children_ids


def test_docling_cache_round_trip(docling_dataset_document: ParsedDocument) -> None:
    """Verify that docling parsed document serialization and deserialization round trips cleanly."""
    from rag_core.adapters.parser.providers import DoclingParser

    parser = DoclingParser("http://127.0.0.1")
    cache_data = parser.to_cache_data(docling_dataset_document)
    restored = parser.from_cache_data(cache_data)
    assert isinstance(restored, ParsedDocument)
    assert restored.schema_version == docling_dataset_document.schema_version
    assert restored.doc_id == docling_dataset_document.doc_id
