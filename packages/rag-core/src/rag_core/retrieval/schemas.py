from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RetrievedChunk(BaseModel):
    """A chunk retrieved from a knowledge base vector search."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    doc_id: str
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
