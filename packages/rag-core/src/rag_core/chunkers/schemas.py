from typing import Any

from langchain_core.documents import Document
from pydantic import BaseModel, ConfigDict, Field


class ChunkingConfig(BaseModel):
    """Config for parser-aware semantic chunking."""

    model_config = ConfigDict(extra="forbid")

    chunk_size: int = 450
    chunk_overlap: int = 50
    merge_max_chars: int = Field(default=300, description="Maximum size for merged sibling micro-chunks.")
    breadcrumb_depth: int = Field(
        default=3, ge=0, description="Number of trailing headings to prefix to child content."
    )
    include_root_breadcrumb: bool = Field(default=True, description="Keep the root heading when trimming breadcrumbs.")
    breadcrumb_separator: str = " > "


class ChunkedDocument(BaseModel):
    """Chunk ready for embedding/indexing."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    doc_id: str
    page_content: str
    order: int
    source_element_ids: list[str] = Field(default_factory=list)
    page_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_langchain_document(self) -> Document:
        """Convert this chunk to LangChain's Document interface."""

        return Document(
            page_content=self.page_content,
            metadata={
                **self.metadata,
                "chunk_id": self.chunk_id,
                "doc_id": self.doc_id,
                "order": self.order,
                "source_element_ids": self.source_element_ids,
                "page_ids": self.page_ids,
            },
        )
