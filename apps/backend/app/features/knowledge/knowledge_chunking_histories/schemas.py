from uuid import UUID

from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field


class KnowledgeChunkingHistoryBase(BaseModel):
    name: str | None = Field(default=None, description="The name of the knowledge_chunking_history.")
    document_id: UUID = Field(description="The parent document ID.")
    strategy: str = Field(description="The chunking strategy used (e.g. recursive, semantic).")
    chunk_count: int = Field(default=0, description="Number of chunks generated.")
    status: str = Field(description="SUCCESS or FAILED")
    chunking_config: dict | None = Field(default=None, description="The chunking config used.")
    error_message: str | None = Field(default=None, description="Error message if failed.")
    duration_seconds: float | None = Field(default=None, description="Duration in seconds.")


class KnowledgeChunkingHistoryCreate(KnowledgeChunkingHistoryBase):
    pass


class KnowledgeChunkingHistoryPut(KnowledgeChunkingHistoryBase):
    pass


class KnowledgeChunkingHistoryPatch(BaseModel):
    name: str | None = Field(default=None, description="The name of the knowledge_chunking_history.")


class KnowledgeChunkingHistoryRead(UUIDSchemaMixin, TimestampSchemaMixin, KnowledgeChunkingHistoryBase):
    model_config = ConfigDict(from_attributes=True)
