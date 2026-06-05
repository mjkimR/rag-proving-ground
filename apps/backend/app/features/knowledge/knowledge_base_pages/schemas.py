from uuid import UUID

from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBasePageBase(BaseModel):
    document_id: UUID = Field(description="The ID of the document this page belongs to.")
    page_id: str = Field(description="Parser-generated string ID of the page.")
    page_number: int = Field(description="1-based page number.")
    content: str = Field(description="The full raw text content of the page.")
    metadata_info: dict | None = Field(default=None, description="Extra metadata for the page.")

    model_config = ConfigDict(populate_by_name=True)


class KnowledgeBasePageCreate(KnowledgeBasePageBase):
    pass


class KnowledgeBasePagePut(KnowledgeBasePageBase):
    pass


class KnowledgeBasePagePatch(BaseModel):
    document_id: UUID | None = Field(default=None)
    page_id: str | None = Field(default=None)
    page_number: int | None = Field(default=None)
    content: str | None = Field(default=None)
    metadata_info: dict | None = Field(default=None)

    model_config = ConfigDict(populate_by_name=True)


class KnowledgeBasePageRead(UUIDSchemaMixin, TimestampSchemaMixin, KnowledgeBasePageBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
