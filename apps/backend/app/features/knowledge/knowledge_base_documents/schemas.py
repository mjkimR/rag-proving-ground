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


class TaskPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    LOWEST = "lowest"


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
    priority: TaskPriority = Field(
        default=TaskPriority.MEDIUM, description="The processing priority/queue of the document."
    )
    file_hash: str = Field(description="The SHA-256 hash of the file content.")
    document_info: dict | None = Field(default=None, description="File size, path, element count metadata.")
    parsing_config: KnowledgeParsingConfig | None = Field(
        default=None, description="Document-level parsing override config."
    )
    chunking_config: ChunkingConfig | None = Field(default=None, description="Document-level chunking override config.")
    summary: str | None = Field(default=None, description="The summary of the document content.")
    summary_model: str | None = Field(default=None, description="The model used to generate the summary.")
    error_message: str | None = Field(default=None, description="Safe error details if ingestion fails.")


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
    summary: str | None = Field(default=None, description="The summary of the document content.")
    summary_model: str | None = Field(default=None, description="The model used to generate the summary.")
    error_message: str | None = Field(default=None, description="Safe error details if ingestion fails.")


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
    priority: TaskPriority = TaskPriority.MEDIUM


# Alias for compatibility
IngestDocumentMessage = ParseDocumentMessage


class ChunkDocumentMessage(BaseModel):
    """Message payload for async document chunking."""

    document_id: UUID
    knowledge_base_id: UUID
    filename: str
    priority: TaskPriority = TaskPriority.MEDIUM


class EmbedDocumentMessage(BaseModel):
    """Message payload for async document embedding."""

    document_id: UUID
    knowledge_base_id: UUID
    filename: str
    priority: TaskPriority = TaskPriority.MEDIUM


class ReprocessDocumentMessage(BaseModel):
    """Message payload for async document reprocessing."""

    document_id: UUID
    mode: KnowledgeBaseDocumentReprocessMode = KnowledgeBaseDocumentReprocessMode.AUTO


def get_queue_name(priority: str | TaskPriority, stage: str = "parse") -> str:
    """Resolve the RabbitMQ queue name for the given ingestion stage."""
    from rag_core.config import get_rabbitmq_settings

    settings = get_rabbitmq_settings()
    if stage == "chunk":
        return settings.chunk_queue_name
    elif stage == "embed":
        return settings.embed_queue_name
    return settings.parse_queue_name


def map_priority_to_int(priority: str | TaskPriority) -> int:
    """Map TaskPriority enum or string to RabbitMQ native priority integer (1-5)."""
    p_val = priority.value if isinstance(priority, TaskPriority) else priority
    mapping = {
        "critical": 5,
        "high": 4,
        "medium": 3,
        "low": 2,
        "lowest": 1,
    }
    return mapping.get(p_val, 3)


class DocumentChunksRead(BaseModel):
    doc_id: UUID
    total_chunks: int
    chunks: list[str]
