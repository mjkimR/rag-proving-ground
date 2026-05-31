from rag_core.parsers import (
    AssetRef,
    ContentFormat,
    ElementType,
    ParsedDocument,
    ParsedElement,
    parsed_document_to_html,
    parsed_document_to_markdown,
)


def test_parsed_document_to_markdown_prefers_elements_by_default() -> None:
    document = ParsedDocument(
        doc_id="doc",
        parser="unit",
        markdown="# Existing",
        elements=[
            ParsedElement(
                element_id="p1",
                type=ElementType.PARAGRAPH,
                format=ContentFormat.TEXT,
                content="Rendered",
                order=1,
            )
        ],
    )

    assert parsed_document_to_markdown(document) == "Rendered"
    assert document.to_markdown() == "Rendered"
    assert parsed_document_to_markdown(document, prefer_document=True) == "# Existing"


def test_parsed_document_to_markdown_renders_elements() -> None:
    document = ParsedDocument(
        doc_id="doc",
        parser="unit",
        elements=[
            ParsedElement(
                element_id="h1",
                type=ElementType.HEADING,
                format=ContentFormat.MARKDOWN,
                content="Already stripped",
                level=2,
                order=2,
            ),
            ParsedElement(
                element_id="t1",
                type=ElementType.TABLE,
                format=ContentFormat.HTML,
                content="<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>",
                order=3,
            ),
            ParsedElement(
                element_id="i1",
                type=ElementType.IMAGE,
                format=ContentFormat.ASSET_REF,
                content="Chart",
                asset=AssetRef(uri="s3://bucket/chart.png"),
                order=4,
            ),
        ],
    )

    assert parsed_document_to_markdown(document) == "\n\n".join(
        [
            "## Already stripped",
            "| A | B |\n| --- | --- |\n| 1 | 2 |",
            "![Chart](s3://bucket/chart.png)",
        ]
    )


def test_parsed_document_to_html_prefers_elements_by_default() -> None:
    document = ParsedDocument(
        doc_id="doc",
        parser="unit",
        html="<article>Existing</article>",
        markdown="# Rendered",
        elements=[
            ParsedElement(
                element_id="p1",
                type=ElementType.PARAGRAPH,
                format=ContentFormat.TEXT,
                content="Rendered",
                order=1,
            )
        ],
    )

    assert parsed_document_to_html(document) == "<p>Rendered</p>"
    assert document.to_html() == "<p>Rendered</p>"
    assert parsed_document_to_html(document, prefer_document=True) == "<article>Existing</article>"


def test_parsed_document_to_markdown_falls_back_to_document_markdown_without_elements() -> None:
    document = ParsedDocument(doc_id="doc", parser="unit", markdown="# Existing")

    assert parsed_document_to_markdown(document) == "# Existing"


def test_parsed_document_to_html_renders_elements_and_full_document() -> None:
    document = ParsedDocument(
        doc_id="doc",
        parser="unit",
        elements=[
            ParsedElement(
                element_id="h1",
                type=ElementType.HEADING,
                format=ContentFormat.MARKDOWN,
                content="# Title",
                level=1,
                order=1,
            ),
            ParsedElement(
                element_id="l1",
                type=ElementType.LIST,
                format=ContentFormat.MARKDOWN,
                content="- first\n- second",
                order=2,
            ),
            ParsedElement(
                element_id="p1",
                type=ElementType.PARAGRAPH,
                format=ContentFormat.TEXT,
                content="Plain text",
                order=3,
            ),
        ],
    )

    html = parsed_document_to_html(document, title="Doc")

    assert "<title>Doc</title>" in html
    assert "<h1>Title</h1>" in html
    assert "<ul><li>first</li><li>second</li></ul>" in html
    assert "<p>Plain text</p>" in html


def test_parsed_document_to_markdown_filters_ignored_elements() -> None:
    document = ParsedDocument(
        doc_id="doc",
        parser="unit",
        elements=[
            ParsedElement(
                element_id="h1",
                type=ElementType.HEADING,
                format=ContentFormat.MARKDOWN,
                content="Title",
                level=1,
                order=1,
                ignored=False,
            ),
            ParsedElement(
                element_id="hdr",
                type=ElementType.PAGE_HEADER,
                format=ContentFormat.MARKDOWN,
                content="Running Header",
                order=2,
                ignored=True,
            ),
            ParsedElement(
                element_id="p1",
                type=ElementType.PARAGRAPH,
                format=ContentFormat.TEXT,
                content="Main text content",
                order=3,
                ignored=False,
            ),
        ],
    )

    # By default (include_ignored=False), layout elements are filtered out
    assert parsed_document_to_markdown(document) == "# Title\n\nMain text content"
    assert parsed_document_to_html(document) == "<h1>Title</h1>\n<p>Main text content</p>"

    # When include_ignored=True, layout elements are included
    assert (
        parsed_document_to_markdown(document, include_ignored=True) == "# Title\n\nRunning Header\n\nMain text content"
    )
    assert (
        parsed_document_to_html(document, include_ignored=True)
        == "<h1>Title</h1>\n<p>Running Header</p>\n<p>Main text content</p>"
    )
