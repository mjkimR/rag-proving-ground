import pytest
from rag_core.adapters.parser.instance import get_parser, parse_document
from rag_core.adapters.parser.interface import ParserInput
from rag_core.adapters.parser.providers.native_text.parser import NativeTextParser
from rag_core.config import get_native_text_parser_settings
from rag_core.parsers.config import KnowledgeParsingConfig, knowledge_parsing_config_hash
from rag_core.parsers.schemas import ContentFormat, ElementType, ParsedDocument


@pytest.fixture(autouse=True)
def mock_storage_and_cache(mocker) -> None:
    mock_client = mocker.AsyncMock()
    mock_client.file_exists = mocker.AsyncMock(return_value=False)
    mock_client.upload_file = mocker.AsyncMock()
    mock_client.download_file = mocker.AsyncMock()

    from rag_core.adapters.parser.cache import ParserCache

    cache = ParserCache(mock_client)
    mocker.patch("rag_core.adapters.parser.instance._get_cache", return_value=cache)


async def test_native_text_parser_plain_text() -> None:

    text_content = "Paragraph 1\n\nParagraph 2\n\nParagraph 3"
    parser_input = ParserInput(
        content=text_content.encode("utf-8"),
        filename="test_doc.txt",
        content_type="text/plain",
    )

    parser = NativeTextParser(max_page_chars=50)
    result: ParsedDocument = await parser.parse(parser_input)

    assert result.parser == "native_text"
    assert result.filename == "test_doc.txt"
    assert len(result.elements) == 3
    assert all(el.type == ElementType.PARAGRAPH for el in result.elements)
    assert all(el.format == ContentFormat.TEXT for el in result.elements)

    # Page splitting validation
    # Max page chars = 50. len("Paragraph 1") == 11.
    # Page 1: Paragraph 1 (11 chars) + Paragraph 2 (11 chars) = 22 chars
    # Since adding Paragraph 3 (11 chars) would be 33, which is still < 50, they all fit on one page!
    assert len(result.pages) == 1
    assert result.elements[0].page_id == result.pages[0].page_id


async def test_native_text_parser_markdown() -> None:
    md_content = """# Heading 1

Some paragraph with *italic* and **bold** text.

- Item A
- Item B

| Header 1 | Header 2 |
|---|---|
| Value 1 | Value 2 |

```python
# Code block
print("Hello")
```
"""
    parser_input = ParserInput(
        content=md_content.encode("utf-8"),
        filename="doc.md",
        content_type="text/markdown",
    )

    parser = NativeTextParser(max_page_chars=2000)
    result: ParsedDocument = await parser.parse(parser_input)

    assert result.parser == "native_text"
    assert len(result.elements) == 5

    # 1. Heading
    assert result.elements[0].type == ElementType.HEADING
    assert result.elements[0].level == 1
    assert result.elements[0].content == "Heading 1"

    # 2. Paragraph
    assert result.elements[1].type == ElementType.PARAGRAPH
    assert "Some paragraph" in result.elements[1].content

    # 3. List
    assert result.elements[2].type == ElementType.LIST
    assert "- Item A" in result.elements[2].content
    assert "- Item B" in result.elements[2].content

    # 4. Table
    assert result.elements[3].type == ElementType.TABLE
    assert result.elements[3].format == ContentFormat.HTML
    assert "<table>" in result.elements[3].content
    assert "<td>Value 1</td>" in result.elements[3].content

    # 5. Code block
    assert result.elements[4].type == ElementType.PARAGRAPH
    assert result.elements[4].format == ContentFormat.MARKDOWN
    assert "```python" in result.elements[4].content


async def test_native_text_parser_html() -> None:
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Ignored Head Title</title>
    <meta name="description" content="Ignored description">
</head>
<body>
    <nav>
        <a href="#home">Ignored Home Link</a>
    </nav>
    <h1>Welcome Header</h1>
    <p>This is paragraph text.</p>
    <aside>
        <p>Ignored sidebar text.</p>
    </aside>
    <script>
        console.log("ignored script");
    </script>
    <style>
        body { color: red; }
    </style>
    <footer>
        <p>Ignored footer text.</p>
    </footer>
</body>
</html>
"""
    parser_input = ParserInput(
        content=html_content.encode("utf-8"),
        filename="index.html",
        content_type="text/html",
    )

    parser = NativeTextParser(max_page_chars=1000)
    result: ParsedDocument = await parser.parse(parser_input)

    assert result.parser == "native_text"

    # Validate elements are created, and ignored tags have ignored=True
    headings = [el for el in result.elements if el.type == ElementType.HEADING]
    assert len(headings) == 1
    assert headings[0].content == "Welcome Header"
    assert headings[0].ignored is False

    non_ignored = [el for el in result.elements if not el.ignored]
    # We should have Heading, paragraph
    assert len(non_ignored) == 2
    assert non_ignored[0].type == ElementType.HEADING
    assert non_ignored[1].type == ElementType.PARAGRAPH
    assert non_ignored[1].content == "This is paragraph text."

    # Meta, script, style, nav, footer, aside elements should have ignored=True
    ignored_elements = [el for el in result.elements if el.ignored]
    assert len(ignored_elements) > 0
    assert any("Ignored Home Link" in el.content for el in ignored_elements)
    assert any("Ignored sidebar text" in el.content for el in ignored_elements)
    assert any("console.log" in el.content for el in ignored_elements)


async def test_native_text_parser_fallback() -> None:
    # Trigger fallback by raising exception in parser input
    bad_input = ParserInput(
        content=b"Some random text",
        filename="broken.txt",
        content_type="text/plain",
    )

    # Subclass and break internal parse method
    class BrokenParser(NativeTextParser):
        def _parse_plain_text(self, text: str, doc_id: str):
            raise ValueError("Forced error for fallback test")

    parser = BrokenParser(max_page_chars=1000)
    result = await parser.parse(bad_input)

    # Should fall back to a single element holding the text
    assert len(result.elements) == 1
    assert result.elements[0].type == ElementType.PARAGRAPH
    assert result.elements[0].content == "Some random text"


async def test_native_text_parser_auto_routing() -> None:
    # When provider is None, a text input is routed to native_text
    parser_input = ParserInput(
        content=b"Hello plain text",
        filename="hello.txt",
        content_type="text/plain",
    )

    # Let's check get_parser with provider=None vs native_text
    parser_auto = get_parser(provider=None)
    assert parser_auto.name == "docling"  # Configured default is docling

    # Let's check parse_document auto routing behavior
    # parse_document will set provider="native_text" automatically internally
    result = await parse_document(parser_input, provider=None)
    assert result.parser == "native_text"


def test_native_text_parser_config_hash() -> None:
    # Changing max_page_chars should change the hash of KnowledgeParsingConfig
    config_1 = KnowledgeParsingConfig(provider="native_text")
    hash_1 = knowledge_parsing_config_hash(config_1)

    settings = get_native_text_parser_settings()
    original_val = settings.max_page_chars

    try:
        # Override setting manually to verify hash change
        settings.max_page_chars = 5000
        config_2 = KnowledgeParsingConfig(provider="native_text")
        hash_2 = knowledge_parsing_config_hash(config_2)

        assert hash_1 != hash_2
    finally:
        # Restore setting
        settings.max_page_chars = original_val


async def test_native_text_parser_ssrf_mitigation() -> None:
    parser = NativeTextParser()

    # loopback
    parser_input_loopback = ParserInput(
        source="http://127.0.0.1:8000/document.txt",
    )
    with pytest.raises(ValueError, match="SSRF Prevention"):
        await parser.parse(parser_input_loopback)

    # private IP
    parser_input_private = ParserInput(
        source="http://192.168.1.50/document.txt",
    )
    with pytest.raises(ValueError, match="SSRF Prevention"):
        await parser.parse(parser_input_private)

    # local hostname
    parser_input_localhost = ParserInput(
        source="http://localhost:8000/document.txt",
    )
    with pytest.raises(ValueError, match="SSRF Prevention"):
        await parser.parse(parser_input_localhost)


async def test_native_text_parser_ssrf_dns_rebinding_mock(mocker) -> None:
    import httpcore
    from rag_core.adapters.parser.providers.shared.network_security import SafeAsyncNetworkBackend

    backend = SafeAsyncNetworkBackend()

    # Mock getaddrinfo to return a loopback/private IP
    mocker.patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 80))])
    with pytest.raises(httpcore.ConnectError, match="SSRF Prevention"):
        await backend.connect_tcp("example.com", 80)

    # Mock getaddrinfo to return a private IP
    mocker.patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("10.0.0.1", 80))])
    with pytest.raises(httpcore.ConnectError, match="SSRF Prevention"):
        await backend.connect_tcp("example.com", 80)

    # Mock getaddrinfo to return a DNS resolution failure
    mocker.patch("socket.getaddrinfo", side_effect=Exception("DNS lookup failed"))
    with pytest.raises(httpcore.ConnectError, match="DNS resolution failed"):
        await backend.connect_tcp("invalid-domain.local", 80)


async def test_native_text_parser_html_comments() -> None:
    html_content = "<p>Hello<!-- this is a comment --> World</p>"
    parser_input = ParserInput(
        content=html_content.encode("utf-8"),
        filename="comments.html",
        content_type="text/html",
    )
    parser = NativeTextParser()
    result = await parser.parse(parser_input)
    # verify comment content is NOT parsed
    assert len(result.elements) == 1
    assert result.elements[0].content == "Hello World"


async def test_native_text_parser_markdown_extensions() -> None:
    # 1. Indented code block
    # 2. Raw HTML block
    md_content = """
    print("hello")

<div>Raw HTML Block</div>
"""
    parser_input = ParserInput(
        content=md_content.encode("utf-8"),
        filename="doc.md",
        content_type="text/markdown",
    )
    parser = NativeTextParser()
    result = await parser.parse(parser_input)
    assert len(result.elements) == 2
    # Verify code block element
    assert result.elements[0].type == ElementType.PARAGRAPH
    assert result.elements[0].format == ContentFormat.MARKDOWN
    assert 'print("hello")' in result.elements[0].content
    # Verify HTML block element
    assert result.elements[1].type == ElementType.PARAGRAPH
    assert result.elements[1].format == ContentFormat.HTML
    assert "Raw HTML Block" in result.elements[1].content


async def test_native_text_parser_html_chunking() -> None:
    # Large HTML containing a paragraph of 70000 chars, larger than 64KB chunk size
    large_text = "A" * 70000
    html_content = f"<p>{large_text}</p>"
    parser_input = ParserInput(
        content=html_content.encode("utf-8"),
        filename="large.html",
        content_type="text/html",
    )
    parser = NativeTextParser(max_page_chars=100000)
    result = await parser.parse(parser_input)
    assert len(result.elements) == 1
    assert result.elements[0].content == large_text
