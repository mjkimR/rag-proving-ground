import hashlib
import json
from collections.abc import Mapping
from typing import Any

from langchain_core.documents import Document
from pydantic import BaseModel, ConfigDict, Field


class ChunkingConfig(BaseModel):
    """Config for parser-aware semantic chunking."""

    model_config = ConfigDict(extra="allow")

    chunk_size: int = 450
    chunk_overlap: int = 50
    merge_max_chars: int = Field(default=300, description="Maximum size for merged sibling micro-chunks.")
    breadcrumb_depth: int = Field(
        default=3, ge=0, description="Number of trailing headings to prefix to child content."
    )
    include_root_breadcrumb: bool = Field(default=True, description="Keep the root heading when trimming breadcrumbs.")
    breadcrumb_separator: str = " > "
    enable_contextual_retrieval: bool = Field(
        default=False,
        description="If true, generates a summary of the document to prepend to all chunks.",
    )
    contextual_retrieval_model: str | None = Field(
        default=None,
        description="Optional specific LLM model to use for contextual retrieval summaries.",
    )
    enrichment: dict[str, Any] | None = Field(
        default=None,
        description="Optional configuration for future chunk enrichment methods.",
    )


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


def resolve_chunking_config(config: ChunkingConfig | Mapping[str, Any] | None) -> ChunkingConfig:
    """Validate and resolve chunking config."""
    if isinstance(config, ChunkingConfig):
        return config
    if config is None:
        return ChunkingConfig()
    return ChunkingConfig.model_validate(config)


def knowledge_chunking_config_hash(config: ChunkingConfig) -> str:
    """Create the stable hash used to identify a chunking configuration."""
    dumped_dict = config.model_dump(mode="json", exclude_none=True)
    serialized = json.dumps(
        dumped_dict,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
