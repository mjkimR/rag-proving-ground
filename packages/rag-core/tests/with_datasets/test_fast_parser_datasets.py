from pathlib import Path

import pytest
from rag_core.parsers.schemas import ElementType, ParsedDocument

pytestmark = pytest.mark.parser


def test_no_unknown_elements(any_dataset_document: ParsedDocument) -> None:
    """Verify that no parsed elements have ElementType.UNKNOWN semantic type for any parser."""
    for element in any_dataset_document.elements:
        assert element.type != ElementType.UNKNOWN, (
            f"Element {element.element_id} in {any_dataset_document.filename} "
            f"parsed by '{any_dataset_document.parser}' has UNKNOWN type: content='{element.content}'"
        )


def normalize_text(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')  # noqa: RUF001
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬀ", "ff").replace("ﬃ", "ffi")
    return " ".join(text.split())


def test_text_completeness(
    any_dataset_document: ParsedDocument,
    critical_snippets: dict[str, list[str]],
) -> None:
    """Verify that critical text snippets are fully preserved after parsing for the reference docling parser,
    and non-trivial text is extracted for all other parsers.
    """
    parser_name = any_dataset_document.parser
    if parser_name != "docling":
        # Verify that fast parsers extract non-trivial text content without checking docling-specific snippets
        assert any_dataset_document.text and len(any_dataset_document.text.strip()) > 100, (
            f"Parser '{parser_name}' extracted empty or trivial text for {any_dataset_document.filename}"
        )
        return

    filename = any_dataset_document.filename or ""
    stem = Path(filename).stem
    if not stem or stem not in critical_snippets:
        pytest.skip(f"No critical snippets mapped for stem: {stem}")

    # Use include_ignored=True to ensure boilerplate page headers are searched
    full_markdown = any_dataset_document.to_markdown(include_ignored=True)
    normalized_markdown = normalize_text(full_markdown)

    for snippet in critical_snippets[stem]:
        normalized_snippet = normalize_text(snippet)
        assert normalized_snippet in normalized_markdown, (
            f"Text completeness validation failed in {filename} with parser '{parser_name}': "
            f"missing critical snippet '{snippet}'"
        )


def test_generic_cache_round_trip(any_dataset_document: ParsedDocument) -> None:
    """Verify that parsed document serialization and deserialization round trips cleanly for all providers."""
    from rag_core.adapters.parser.factory import ParserFactory

    provider_name = any_dataset_document.parser
    parser = ParserFactory.create_parser(provider=provider_name)

    cache_data = parser.to_cache_data(any_dataset_document)
    restored = parser.from_cache_data(cache_data)
    assert isinstance(restored, ParsedDocument)
    assert restored.schema_version == any_dataset_document.schema_version
    assert restored.doc_id == any_dataset_document.doc_id
    assert restored.parser == any_dataset_document.parser


def test_document_structure_integrity(any_dataset_document: ParsedDocument) -> None:
    """Verify elements have correct page references, unique IDs, and sequence ordering."""
    doc = any_dataset_document
    page_ids = {p.page_id for p in doc.pages}
    assert len(page_ids) == len(doc.pages), "Duplicate page IDs found in doc.pages"

    element_ids = set()
    for idx, el in enumerate(doc.elements):
        assert el.order == idx, f"Element order {el.order} doesn't match list index {idx}"
        assert el.page_id in page_ids, f"Element references non-existent page ID: {el.page_id}"
        assert el.element_id not in element_ids, f"Duplicate element ID: {el.element_id}"
        element_ids.add(el.element_id)
