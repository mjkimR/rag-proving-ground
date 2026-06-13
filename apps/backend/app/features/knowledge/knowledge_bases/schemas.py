from enum import StrEnum
from typing import Any, Self
from uuid import UUID

from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from rag_core.chunkers import ChunkingConfig
from rag_core.embeddings import KnowledgeEmbeddingConfig, RetrievalMode
from rag_core.parsers import KnowledgeParsingConfig
from rag_core.retrieval import RerankerConfig


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
    retrieval_mode: RetrievalMode | None = Field(
        default=None, description="Query-time override for retrieval mode (dense, sparse, hybrid)"
    )
    sparse_model: str | None = Field(default=None, description="Query-time override for sparse embedding model")


class MultiKnowledgeBaseSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="The search query.")
    knowledge_base_ids: list[UUID] = Field(
        ...,
        min_length=1,
        description="Knowledge bases to search. Duplicate IDs are removed while preserving request order.",
    )
    limit: int = Field(default=5, ge=1, le=100, description="The maximum number of search results to return.")
    candidate_limit: int | None = Field(
        default=None,
        ge=1,
        le=500,
        description="Initial vector candidates to retrieve per knowledge base before final merging and reranking.",
    )
    reranker_config: RerankerConfig | None = Field(default=None, description="Reranker options for merged results.")
    retrieval_mode: RetrievalMode | None = Field(
        default=None, description="Query-time override for retrieval mode (dense, sparse, hybrid)"
    )
    sparse_model: str | None = Field(default=None, description="Query-time override for sparse embedding model")

    @field_validator("knowledge_base_ids")
    @classmethod
    def dedupe_knowledge_base_ids(cls, value: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def require_reranker_for_multi_kb(self) -> Self:
        if len(self.knowledge_base_ids) >= 2 and self.reranker_config is None:
            raise ValueError("reranker_config is required when searching multiple knowledge bases.")
        if (
            self.reranker_config is not None
            and self.reranker_config.top_n is not None
            and self.reranker_config.top_n < self.limit
        ):
            raise ValueError("reranker_config.top_n must be greater than or equal to limit.")
        return self


class KnowledgeBaseSearchResultItem(BaseModel):
    chunk_id: str = Field(description="The unique identifier for the chunk.")
    doc_id: str = Field(description="The unique identifier for the document containing the chunk.")
    content: str = Field(description="The text content of the chunk.")
    score: float = Field(description="The final ranking score.")
    knowledge_base_id: UUID = Field(description="The knowledge base that produced the chunk.")
    vector_score: float = Field(description="The original vector search score.")
    rerank_score: float | None = Field(default=None, description="The reranker relevance score when reranking is used.")
    page_content: str | None = Field(
        default=None, description="The full parent page text content of the chunk, if resolved."
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata associated with the chunk.")


class KnowledgeBaseSearchResponse(BaseModel):
    query: str = Field(description="The original search query.")
    results: list[KnowledgeBaseSearchResultItem] = Field(description="The list of search results.")
    total: int = Field(description="The total number of results found.")
