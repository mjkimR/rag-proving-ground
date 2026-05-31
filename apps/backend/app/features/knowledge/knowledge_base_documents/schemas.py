from uuid import UUID

from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBaseDocumentBase(BaseModel):
    name: str = Field(description="The name of the knowledge_base_document.")
    knowledge_base_id: UUID = Field(description="The ID of the parent knowledge base.")
    status: str = Field(default="READY", description="The status of document processing.")
    file_md5: str = Field(description="The MD5 hash of the file content.")
    document_info: dict | None = Field(default=None, description="File size, path, element count metadata.")
    parsing_config: dict | None = Field(default=None, description="Document-level parsing override config.")
    chunking_config: dict | None = Field(default=None, description="Document-level chunking override config.")


class KnowledgeBaseDocumentCreate(KnowledgeBaseDocumentBase):
    pass


class KnowledgeBaseDocumentPut(KnowledgeBaseDocumentBase):
    pass


class KnowledgeBaseDocumentPatch(BaseModel):
    name: str | None = Field(default=None, description="The name of the document.")
    status: str | None = Field(default=None, description="The status of document processing.")
    parsing_config: dict | None = Field(default=None, description="Document-level parsing override config.")
    chunking_config: dict | None = Field(default=None, description="Document-level chunking override config.")


class KnowledgeBaseDocumentRead(UUIDSchemaMixin, TimestampSchemaMixin, KnowledgeBaseDocumentBase):
    model_config = ConfigDict(from_attributes=True)
