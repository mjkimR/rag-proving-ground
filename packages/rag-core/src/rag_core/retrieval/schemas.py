from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RerankerConfig(BaseModel):
    """Safe client-controlled reranker options."""

    model_config = ConfigDict(extra="forbid")

    model: str | None = Field(default=None, description="Reranker model name. Uses the runtime default when omitted.")
    top_n: int | None = Field(default=None, ge=1, le=100, description="Maximum number of reranked results to return.")


class RetrievedChunk(BaseModel):
    """A chunk retrieved from a knowledge base vector search."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    doc_id: str
    content: str
    score: float
    knowledge_base_id: UUID
    vector_score: float
    rerank_score: float | None = None
    page_content: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
