from enum import StrEnum
from uuid import UUID

from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field
from rag_core.chunkers import ChunkingConfig
from rag_core.parsers import KnowledgeParsingConfig


class KnowledgeBaseDocumentStatus(StrEnum):
    READY = "READY"
    QUEUED = "QUEUED"
    PARSING = "PARSING"
    CHUNKING = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    PENDING_REPARSE = "PENDING_REPARSE"
    PENDING_RECHUNK = "PENDING_RECHUNK"
    PENDING_REEMBED = "PENDING_REEMBED"
    DELETING = "DELETING"


class KnowledgeBaseDocumentReprocessMode(StrEnum):
    AUTO = "AUTO"
    REPARSE = "REPARSE"
    RECHUNK = "RECHUNK"
    REEMBED = "REEMBED"


class KnowledgeBaseDocumentReprocessRequest(BaseModel):
    mode: KnowledgeBaseDocumentReprocessMode = Field(
        default=KnowledgeBaseDocumentReprocessMode.AUTO,
        description="Reprocessing mode. AUTO uses the document pending status.",
    )


class KnowledgeBaseDocumentBase(BaseModel):
    name: str = Field(description="The name of the knowledge_base_document.")
    knowledge_base_id: UUID = Field(description="The ID of the parent knowledge base.")
    status: KnowledgeBaseDocumentStatus = Field(
        default=KnowledgeBaseDocumentStatus.READY, description="The status of document processing."
    )
    file_hash: str = Field(description="The SHA-256 hash of the file content.")
    document_info: dict | None = Field(default=None, description="File size, path, element count metadata.")
    parsing_config: KnowledgeParsingConfig | None = Field(
        default=None, description="Document-level parsing override config."
    )
    chunking_config: ChunkingConfig | None = Field(default=None, description="Document-level chunking override config.")


class KnowledgeBaseDocumentCreate(KnowledgeBaseDocumentBase):
    pass


class KnowledgeBaseDocumentPut(KnowledgeBaseDocumentBase):
    pass


class KnowledgeBaseDocumentPatch(BaseModel):
    name: str | None = Field(default=None, description="The name of the document.")
    status: KnowledgeBaseDocumentStatus | None = Field(default=None, description="The status of document processing.")
    parsing_config: KnowledgeParsingConfig | None = Field(
        default=None, description="Document-level parsing override config."
    )
    chunking_config: ChunkingConfig | None = Field(default=None, description="Document-level chunking override config.")


class KnowledgeBaseDocumentRead(UUIDSchemaMixin, TimestampSchemaMixin, KnowledgeBaseDocumentBase):
    model_config = ConfigDict(from_attributes=True)


class ParseDocumentMessage(BaseModel):
    """Message payload for async document parsing."""

    document_id: UUID
    knowledge_base_id: UUID
    file_hash: str
    filename: str
    content_type: str | None = None
    provider: str | None = None


# Alias for compatibility
IngestDocumentMessage = ParseDocumentMessage


class ChunkDocumentMessage(BaseModel):
    """Message payload for async document chunking."""

    document_id: UUID
    knowledge_base_id: UUID
    filename: str


class EmbedDocumentMessage(BaseModel):
    """Message payload for async document embedding."""

    document_id: UUID
    knowledge_base_id: UUID
    filename: str


class ReprocessDocumentMessage(BaseModel):
    """Message payload for async document reprocessing."""

    document_id: UUID
    mode: KnowledgeBaseDocumentReprocessMode = KnowledgeBaseDocumentReprocessMode.AUTO
