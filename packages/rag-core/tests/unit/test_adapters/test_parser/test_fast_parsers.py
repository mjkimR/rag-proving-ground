from unittest.mock import AsyncMock, patch

import pytest
from rag_core.adapters.parser.interface import ParserInput
from rag_core.adapters.parser.providers.pdf_oxide.parser import PdfOxideParser
from rag_core.adapters.parser.providers.pymupdf4llm.parser import PyMuPDF4LLMParser
from rag_core.adapters.parser.providers.shared.fetcher import get_input_bytes
from rag_core.parsers.schemas import ContentFormat, ElementType


@pytest.fixture(autouse=True)
def mock_storage_and_cache(mocker) -> None:
    mock_client = mocker.AsyncMock()
    mock_client.file_exists = mocker.AsyncMock(return_value=False)
    mock_client.upload_file = mocker.AsyncMock()
    mock_client.download_file = mocker.AsyncMock()

    from rag_core.adapters.parser.cache import ParserCache

    cache = ParserCache(mock_client)
    mocker.patch("rag_core.adapters.parser.instance._get_cache", return_value=cache)


async def test_get_input_bytes_content() -> None:
    parser_input = ParserInput(content=b"hello", filename="test.txt")
    data = await get_input_bytes(parser_input)
    assert data == b"hello"


async def test_get_input_bytes_file(tmp_path) -> None:
    test_file = tmp_path / "sample.pdf"
    test_file.write_bytes(b"%PDF mock content")

    parser_input = ParserInput(source=str(test_file))
    data = await get_input_bytes(parser_input)
    assert data == b"%PDF mock content"


async def test_get_input_bytes_url(mocker) -> None:
    mock_response = mocker.MagicMock()
    mock_response.content = b"http body bytes"
    mock_response.raise_for_status = mocker.MagicMock()

    mock_client = mocker.AsyncMock()
    mock_client.get.return_value = mock_response

    mocker.patch(
        "rag_core.adapters.parser.providers.shared.fetcher.get_safe_http_client",
        return_value=mock_client,
    )
    mocker.patch("rag_core.adapters.parser.providers.shared.fetcher._validate_ssrf")

    parser_input = ParserInput(source="https://safe-domain.com/sample.pdf")
    data = await get_input_bytes(parser_input)
    assert data == b"http body bytes"


@patch("rag_core.adapters.parser.providers.pymupdf4llm.parser.get_http_client")
async def test_pymupdf4llm_parser_success(mock_get_client, mocker) -> None:
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {
        "engine": "pymupdf4llm",
        "markdown": "# Header 1\n\nPage 1 text\n\n---\n\nPage 2 text",
        "pages": [{"page_no": 1, "text": "# Header 1\n\nPage 1 text"}, {"page_no": 2, "text": "Page 2 text"}],
    }
    mock_response.raise_for_status = mocker.MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_get_client.return_value = mock_client

    parser = PyMuPDF4LLMParser(base_url="http://mock-fast-parser")
    parser_input = ParserInput(content=b"pdf_bytes", filename="doc.pdf")

    result = await parser.parse(parser_input)

    assert result.parser == "pymupdf4llm"
    assert result.markdown == "# Header 1\n\nPage 1 text\n\n---\n\nPage 2 text"
    assert len(result.pages) == 2
    assert result.pages[0].page_no == 1
    assert result.pages[1].page_no == 2

    # Expecting elements:
    # Page 1: Heading ("Header 1"), Paragraph ("Page 1 text")
    # Page 2: Paragraph ("Page 2 text")
    assert len(result.elements) == 3

    assert result.elements[0].type == ElementType.HEADING
    assert result.elements[0].content == "Header 1"
    assert result.elements[0].page_id == result.pages[0].page_id

    assert result.elements[1].type == ElementType.PARAGRAPH
    assert result.elements[1].content == "Page 1 text"
    assert result.elements[1].page_id == result.pages[0].page_id

    assert result.elements[2].type == ElementType.PARAGRAPH
    assert result.elements[2].content == "Page 2 text"
    assert result.elements[2].page_id == result.pages[1].page_id

    # Check order assignment
    assert [el.order for el in result.elements] == [0, 1, 2]
    assert [el.element_id for el in result.elements] == ["doc_el_0", "doc_el_1", "doc_el_2"]


@patch("rag_core.adapters.parser.providers.pymupdf4llm.parser.get_http_client")
async def test_pymupdf4llm_parser_with_page_boxes_success(mock_get_client, mocker) -> None:
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {
        "engine": "pymupdf4llm",
        "markdown": "# Header 1\n\nPage 1 text",
        "pages": [
            {
                "page_no": 1,
                "text": "# Header 1\n\nPage 1 text",
                "page_boxes": [
                    {"index": 0, "class": "section-header", "bbox": [10.0, 20.0, 30.0, 40.0], "pos": [0, 10]},
                    {"index": 1, "class": "text", "bbox": [15.0, 25.0, 35.0, 45.0], "pos": [12, 23]},
                ],
            }
        ],
    }
    mock_response.raise_for_status = mocker.MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_get_client.return_value = mock_client

    parser = PyMuPDF4LLMParser(base_url="http://mock-fast-parser")
    parser_input = ParserInput(content=b"pdf_bytes", filename="doc.pdf")

    result = await parser.parse(parser_input)

    assert result.parser == "pymupdf4llm"
    assert len(result.pages) == 1
    assert len(result.elements) == 2

    # Verify first element (heading)
    assert result.elements[0].type == ElementType.HEADING
    assert result.elements[0].content == "Header 1"
    assert result.elements[0].level == 1
    assert result.elements[0].bbox is not None
    assert result.elements[0].bbox.left == 10.0
    assert result.elements[0].bbox.top == 20.0
    assert result.elements[0].bbox.right == 30.0
    assert result.elements[0].bbox.bottom == 40.0

    # Verify second element (paragraph)
    assert result.elements[1].type == ElementType.PARAGRAPH
    assert result.elements[1].content == "Page 1 text"
    assert result.elements[1].bbox is not None
    assert result.elements[1].bbox.left == 15.0
    assert result.elements[1].bbox.top == 25.0
    assert result.elements[1].bbox.right == 35.0
    assert result.elements[1].bbox.bottom == 45.0


@patch("rag_core.adapters.parser.providers.pdf_oxide.parser.get_http_client")
async def test_pdf_oxide_parser_success(mock_get_client, mocker) -> None:
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {"engine": "pdf_oxide", "pages": [{"page_no": 1, "text": "Page 1 content"}]}
    mock_response.raise_for_status = mocker.MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_get_client.return_value = mock_client

    parser = PdfOxideParser(base_url="http://mock-fast-parser")
    parser_input = ParserInput(content=b"pdf_bytes", filename="doc.pdf")

    result = await parser.parse(parser_input)

    assert result.parser == "pdf_oxide"
    assert len(result.pages) == 1
    assert len(result.elements) == 1
    assert result.elements[0].content == "Page 1 content"


@patch("rag_core.adapters.parser.providers.pdf_oxide.parser.get_http_client")
async def test_pdf_oxide_parser_with_page_boxes_success(mock_get_client, mocker) -> None:
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {
        "engine": "pdf_oxide",
        "pages": [
            {
                "page_no": 1,
                "text": "Page 1 content text",
                "page_boxes": [{"index": 0, "class": "bodyblock", "bbox": [10.0, 20.0, 30.0, 40.0], "pos": [0, 19]}],
            }
        ],
    }
    mock_response.raise_for_status = mocker.MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_get_client.return_value = mock_client

    parser = PdfOxideParser(base_url="http://mock-fast-parser")
    parser_input = ParserInput(content=b"pdf_bytes", filename="doc.pdf")

    result = await parser.parse(parser_input)

    assert result.parser == "pdf_oxide"
    assert len(result.pages) == 1
    assert len(result.elements) == 1
    assert result.elements[0].content == "Page 1 content text"
    assert result.elements[0].format == ContentFormat.TEXT
    assert result.elements[0].bbox is not None
    assert result.elements[0].bbox.left == 10.0
    assert result.elements[0].bbox.top == 20.0
    assert result.elements[0].bbox.right == 30.0
    assert result.elements[0].bbox.bottom == 40.0
