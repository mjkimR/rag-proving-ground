from uuid import UUID

from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field
from rag_core.parsers import KnowledgeParsingConfig


class KnowledgeParsingHistoryBase(BaseModel):
    name: str | None = Field(default=None, description="The name of the knowledge_parsing_history.")
    document_id: UUID = Field(description="The parent document ID.")
    provider: str | None = Field(default=None, description="Parsing provider (e.g. docling)")
    status: str = Field(description="SUCCESS or FAILED")
    parsing_config: KnowledgeParsingConfig | None = Field(default=None, description="The parsing configurations used.")
    error_message: str | None = Field(default=None, description="Error details if failed.")
    duration_seconds: float | None = Field(default=None, description="Duration in seconds.")


class KnowledgeParsingHistoryCreate(KnowledgeParsingHistoryBase):
    pass


class KnowledgeParsingHistoryPut(KnowledgeParsingHistoryBase):
    pass


class KnowledgeParsingHistoryPatch(BaseModel):
    name: str | None = Field(default=None, description="The name of the knowledge_parsing_history.")


class KnowledgeParsingHistoryRead(UUIDSchemaMixin, TimestampSchemaMixin, KnowledgeParsingHistoryBase):
    model_config = ConfigDict(from_attributes=True)
