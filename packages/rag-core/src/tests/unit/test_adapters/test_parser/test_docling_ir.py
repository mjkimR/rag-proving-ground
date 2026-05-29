import json
from pathlib import Path

from rag_core.adapters.parser.cache import ParserCache
from rag_core.adapters.parser.interface import ParserInput
from rag_core.adapters.parser.normalizers import normalize_docling_document
from rag_core.adapters.parser.providers.docling import DoclingParser
from rag_core.parsers.schemas import ElementType, ParsedDocument

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


def test_parser_cache_uses_schema_version_in_result_path(tmp_path: Path) -> None:
    cache = ParserCache(tmp_path)

    result_path = cache._result_path("abc", "docling", schema_version="1.0")

    assert result_path == tmp_path / "abc" / "docling-1.0.json"


def test_parser_cache_stores_original_file_and_meta_under_hash(tmp_path: Path) -> None:
    cache = ParserCache(tmp_path)
    parser_input = ParserInput(
        content=b"example",
        filename="sample.pdf",
        content_type="application/pdf",
        metadata={"source": "unit"},
    )

    md5_hash = cache.store_file(parser_input)

    cache_dir = tmp_path / md5_hash
    assert (cache_dir / "sample.pdf").read_bytes() == b"example"
    assert json.loads((cache_dir / "meta.json").read_text(encoding="utf-8")) == {
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
