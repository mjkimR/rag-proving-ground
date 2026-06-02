from enum import StrEnum
from typing import Any

from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field
from rag_core.chunkers import ChunkingConfig
from rag_core.embeddings import KnowledgeEmbeddingConfig
from rag_core.parsers import KnowledgeParsingConfig


class KnowledgeBaseConfigApplyMode(StrEnum):
    NEW_ONLY = "NEW_ONLY"
    INHERITED_ONLY = "INHERITED_ONLY"
    FORCE_ALL = "FORCE_ALL"


class KnowledgeBaseStatus(StrEnum):
    READY = "READY"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    DELETING = "DELETING"


class KnowledgeBaseBase(BaseModel):
    name: str = Field(description="The name of the knowledge_base.")
    embedding_config: KnowledgeEmbeddingConfig | None = Field(default=None, description="The embedding config.")
    default_chunking_config: ChunkingConfig | None = Field(default=None, description="The default chunking config.")
    default_parsing_config: KnowledgeParsingConfig | None = Field(
        default=None, description="The default parsing config."
    )


class KnowledgeBaseCreate(KnowledgeBaseBase):
    pass


class KnowledgeBasePut(KnowledgeBaseBase):
    pass


class KnowledgeBasePatch(BaseModel):
    name: str | None = Field(default=None, description="The name of the knowledge_base.")
    status: KnowledgeBaseStatus | None = Field(default=None, description="The status of the knowledge_base.")
    embedding_config: KnowledgeEmbeddingConfig | None = Field(default=None, description="The embedding config.")
    default_chunking_config: ChunkingConfig | None = Field(default=None, description="The default chunking config.")
    default_parsing_config: KnowledgeParsingConfig | None = Field(
        default=None, description="The default parsing config."
    )
    apply_mode: KnowledgeBaseConfigApplyMode = Field(
        default=KnowledgeBaseConfigApplyMode.INHERITED_ONLY,
        description="How config changes are applied to existing documents.",
    )


class KnowledgeBaseRead(UUIDSchemaMixin, TimestampSchemaMixin, KnowledgeBaseBase):
    status: KnowledgeBaseStatus = Field(description="Current status of the knowledge base.")
    embed_config_hash: str | None = Field(default=None, description="Hash signature of the embedding config.")
    model_config = ConfigDict(from_attributes=True)


class KnowledgeBaseSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="The search query.")
    limit: int = Field(default=5, ge=1, le=100, description="The maximum number of search results to return.")


class KnowledgeBaseSearchResultItem(BaseModel):
    chunk_id: str = Field(description="The unique identifier for the chunk.")
    doc_id: str = Field(description="The unique identifier for the document containing the chunk.")
    content: str = Field(description="The text content of the chunk.")
    score: float = Field(description="The similarity score.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata associated with the chunk.")


class KnowledgeBaseSearchResponse(BaseModel):
    query: str = Field(description="The original search query.")
    results: list[KnowledgeBaseSearchResultItem] = Field(description="The list of search results.")
    total: int = Field(description="The total number of results found.")
