"""Parser-agnostic document schema used between parsing and chunking.

The parser layer may receive high-fidelity JSON, HTML, Markdown, or plain/raw
text depending on the provider and source type. This module keeps those
provider outputs available while exposing a stable element model for chunking,
indexing, and retrieval.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

PARSED_DOCUMENT_SCHEMA_VERSION = "1.0"


class ElementType(StrEnum):
    """Normalized semantic categories for parser layout elements."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    IMAGE = "image"
    EQUATION = "equation"
    CAPTION = "caption"
    FOOTNOTE = "footnote"
    PAGE_HEADER = "page_header"
    PAGE_FOOTER = "page_footer"
    SECTION_INDEX = "section_index"
    UNKNOWN = "unknown"


class ContentFormat(StrEnum):
    """Canonical storage format for an element's content field."""

    MARKDOWN = "markdown"
    HTML = "html"
    LATEX = "latex"
    TEXT = "text"
    ASSET_REF = "asset_ref"


class BoundingBox(BaseModel):
    """Element bounds in the parser's original page coordinate space."""

    model_config = ConfigDict(extra="forbid")

    left: float = Field(description="Left coordinate in parser/page coordinate space.")
    top: float = Field(description="Top coordinate in parser/page coordinate space.")
    right: float = Field(description="Right coordinate in parser/page coordinate space.")
    bottom: float = Field(description="Bottom coordinate in parser/page coordinate space.")
    coord_origin: str | None = Field(
        default=None, description="Original coordinate origin, e.g. TOPLEFT or BOTTOMLEFT."
    )


class Provenance(BaseModel):
    """Trace information linking an IR element back to provider output."""

    model_config = ConfigDict(extra="forbid")

    page_no: int | None = None
    bbox: BoundingBox | None = None
    charspan: tuple[int, int] | None = None
    source_ref: str | None = Field(default=None, description="Provider-specific source reference such as #/texts/0.")
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssetRef(BaseModel):
    """Reference to binary or visual data stored outside text content."""

    model_config = ConfigDict(extra="forbid")

    uri: str | None = Field(default=None, description="Resolvable URI for the asset.")
    path: str | None = Field(default=None, description="Storage path when the binary is stored outside the IR.")
    mimetype: str | None = None
    width: float | None = None
    height: float | None = None
    dpi: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParsedPage(BaseModel):
    """Physical or rendered page metadata.

    `page_id` is the join key used by text chunks, page images, and vision
    indexes. For web or text-only sources, adapters may emit one synthetic page.
    """

    model_config = ConfigDict(extra="forbid")

    page_id: str
    page_no: int
    width: float | None = None
    height: float | None = None
    image: AssetRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParsedElement(BaseModel):
    """Smallest parser-normalized unit consumed by chunking.

    `content` should hold the canonical representation described by `format`.
    Examples: headings and paragraphs as Markdown/text, tables as raw
    `<table>...</table>` HTML, equations as LaTeX, and images as `asset_ref`
    plus optional OCR/caption metadata.
    """

    model_config = ConfigDict(extra="forbid")

    element_id: str
    type: ElementType
    format: ContentFormat
    content: str = ""
    page_id: str | None = None
    order: int
    level: int | None = Field(default=None, description="Heading/list nesting level when available.")
    bbox: BoundingBox | None = None
    provenance: list[Provenance] = Field(default_factory=list)
    parent_id: str | None = None
    children_ids: list[str] = Field(default_factory=list)
    asset: AssetRef | None = None
    ignored: bool = Field(
        default=False, description="Whether this element is layout boilerplate and ignored during chunking."
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParsedDocument(BaseModel):
    """Provider-neutral parsed document.

    Mapping policy:
    - `raw`: original provider JSON or response payload for debugging/replay.
    - `html`: document-level HTML when a parser provides it.
    - `markdown`: document-level Markdown when a parser provides it.
    - `text`: plain text or low-fidelity raw text fallback.
    - `elements`: canonical structured representation used by chunking.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = PARSED_DOCUMENT_SCHEMA_VERSION
    doc_id: str
    source: str | None = None
    filename: str | None = None
    mimetype: str | None = None
    parser: str
    pages: list[ParsedPage] = Field(default_factory=list)
    elements: list[ParsedElement] = Field(default_factory=list)
    text: str = ""
    html: str = ""
    markdown: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)

    def elements_for_page(self, page_id: str) -> list[ParsedElement]:
        return [element for element in self.elements if element.page_id == page_id]

    def to_markdown(self, *, prefer_document: bool = False) -> str:
        """Render this document as Markdown."""

        from rag_core.parsers.renderers import parsed_document_to_markdown

        return parsed_document_to_markdown(self, prefer_document=prefer_document)

    def to_html(self, *, prefer_document: bool = False, title: str | None = None) -> str:
        """Render this document as HTML."""

        from rag_core.parsers.renderers import parsed_document_to_html

        return parsed_document_to_html(self, prefer_document=prefer_document, title=title)
