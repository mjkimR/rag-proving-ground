from uuid import UUID

from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field


class SessionKnowledgeBaseBase(BaseModel):
    thread_id: str = Field(description="The Aegra (LangGraph) session or thread ID.")
    knowledge_base_id: UUID = Field(description="The associated KnowledgeBase ID.")


class SessionKnowledgeBaseCreate(SessionKnowledgeBaseBase):
    pass


class SessionKnowledgeBasePut(SessionKnowledgeBaseBase):
    pass


class SessionKnowledgeBasePatch(BaseModel):
    pass


class SessionKnowledgeBaseRead(UUIDSchemaMixin, TimestampSchemaMixin, SessionKnowledgeBaseBase):
    model_config = ConfigDict(from_attributes=True)
