from uuid import UUID

from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field
from rag_core.embeddings import KnowledgeEmbeddingConfig


class KnowledgeEmbeddingHistoryBase(BaseModel):
    name: str | None = Field(default=None, description="The name of the knowledge_embedding_history.")
    document_id: UUID = Field(description="The parent document ID.")
    model_name: str = Field(description="The embedding model used.")
    vector_count: int = Field(default=0, description="The number of vectors indexed.")
    status: str = Field(description="SUCCESS or FAILED")
    embedding_config: KnowledgeEmbeddingConfig | None = Field(default=None, description="The embedding config used.")
    error_message: str | None = Field(default=None, description="Error message if failed.")
    duration_seconds: float | None = Field(default=None, description="Duration in seconds.")


class KnowledgeEmbeddingHistoryCreate(KnowledgeEmbeddingHistoryBase):
    pass


class KnowledgeEmbeddingHistoryPut(KnowledgeEmbeddingHistoryBase):
    pass


class KnowledgeEmbeddingHistoryPatch(BaseModel):
    name: str | None = Field(default=None, description="The name of the knowledge_embedding_history.")


class KnowledgeEmbeddingHistoryRead(UUIDSchemaMixin, TimestampSchemaMixin, KnowledgeEmbeddingHistoryBase):
    model_config = ConfigDict(from_attributes=True)
