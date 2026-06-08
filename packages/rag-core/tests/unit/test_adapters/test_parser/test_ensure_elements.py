from rag_core.adapters.parser.instance import _ensure_elements
from rag_core.parsers.schemas import ContentFormat, ElementType, ParsedDocument


def test_ensure_elements_from_markdown():
    # Arrange
    doc = ParsedDocument(
        doc_id="test_markdown",
        parser="mock_parser",
        markdown="# Heading\n\nSome paragraph.",
        elements=[],
    )

    # Act
    processed = _ensure_elements(doc)

    # Assert
    assert len(processed.elements) == 2
    assert processed.elements[0].type == ElementType.HEADING
    assert processed.elements[0].content == "Heading"
    assert processed.elements[0].level == 1
    assert processed.elements[1].type == ElementType.PARAGRAPH
    assert processed.elements[1].content == "Some paragraph."
    assert len(processed.pages) == 1
    assert processed.elements[0].page_id == processed.pages[0].page_id


def test_ensure_elements_from_html():
    # Arrange
    doc = ParsedDocument(
        doc_id="test_html",
        parser="mock_parser",
        html="<h1>HTML Heading</h1><p>HTML Paragraph</p>",
        elements=[],
    )

    # Act
    processed = _ensure_elements(doc)

    # Assert
    assert len(processed.elements) == 2
    assert processed.elements[0].type == ElementType.HEADING
    assert processed.elements[0].content == "HTML Heading"
    assert processed.elements[0].level == 1
    assert processed.elements[1].type == ElementType.PARAGRAPH
    assert processed.elements[1].content == "HTML Paragraph"
    assert len(processed.pages) == 1


def test_ensure_elements_from_text():
    # Arrange
    doc = ParsedDocument(
        doc_id="test_text",
        parser="mock_parser",
        text="Line 1\n\nLine 2",
        elements=[],
    )

    # Act
    processed = _ensure_elements(doc)

    # Assert
    assert len(processed.elements) == 2
    assert processed.elements[0].type == ElementType.PARAGRAPH
    assert processed.elements[0].content == "Line 1"
    assert processed.elements[1].type == ElementType.PARAGRAPH
    assert processed.elements[1].content == "Line 2"
    assert len(processed.pages) == 1


def test_ensure_elements_already_has_elements():
    # Arrange
    from rag_core.parsers.schemas import ParsedElement

    existing_el = ParsedElement(
        element_id="el_0",
        type=ElementType.PARAGRAPH,
        format=ContentFormat.TEXT,
        content="Existing Element",
        order=0,
    )
    doc = ParsedDocument(
        doc_id="test_existing",
        parser="mock_parser",
        markdown="# This should not be parsed",
        elements=[existing_el],
    )

    # Act
    processed = _ensure_elements(doc)

    # Assert
    assert len(processed.elements) == 1
    assert processed.elements[0].content == "Existing Element"
