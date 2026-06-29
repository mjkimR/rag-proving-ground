from uuid import UUID

from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field


class JobProcessHistoryBase(BaseModel):
    name: str | None = Field(default=None, description="Optional display name for the history event.")
    resource_type: str = Field(description="Logical resource type, for example knowledge_base_document.")
    resource_id: UUID = Field(description="Resource UUID. This is intentionally not a foreign key.")
    group_id: UUID | None = Field(
        default=None, description="Optional group UUID to tie related processes together (e.g. knowledge base ID)."
    )
    stage: str = Field(description="Processing stage, for example parsing, chunking, embedding, or indexing.")
    outcome: str = Field(description="Result of this historical event, for example SUCCESS, FAILED, or SKIPPED.")
    provider: str | None = Field(default=None, description="Optional provider name used for the stage.")
    model_name: str | None = Field(default=None, description="Optional model name used for the stage.")
    config: dict | None = Field(default=None, description="Effective configuration snapshot used for the stage.")
    metrics: dict | None = Field(default=None, description="Stage-specific event metrics.")
    error_message: str | None = Field(default=None, description="Safe error detail for failed events.")
    duration_seconds: float | None = Field(default=None, description="Stage duration in seconds.")


class JobProcessHistoryCreate(JobProcessHistoryBase):
    pass


class JobProcessHistoryPut(JobProcessHistoryBase):
    pass


class JobProcessHistoryPatch(BaseModel):
    name: str | None = Field(default=None, description="Optional display name for the history event.")


class JobProcessHistoryRead(UUIDSchemaMixin, TimestampSchemaMixin, JobProcessHistoryBase):
    model_config = ConfigDict(from_attributes=True)
