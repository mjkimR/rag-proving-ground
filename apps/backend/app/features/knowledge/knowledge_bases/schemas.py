from enum import StrEnum

from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field
from rag_core.chunkers import ChunkingConfig
from rag_core.embeddings import KnowledgeEmbeddingConfig
from rag_core.parsers import KnowledgeParsingConfig


class KnowledgeBaseConfigApplyMode(StrEnum):
    NEW_ONLY = "NEW_ONLY"
    INHERITED_ONLY = "INHERITED_ONLY"
    FORCE_ALL = "FORCE_ALL"


class KnowledgeBaseStatus(StrEnum):
    READY = "READY"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    DELETING = "DELETING"


class KnowledgeBaseBase(BaseModel):
    name: str = Field(description="The name of the knowledge_base.")
    embedding_config: KnowledgeEmbeddingConfig | None = Field(default=None, description="The embedding config.")
    default_chunking_config: ChunkingConfig | None = Field(default=None, description="The default chunking config.")
    default_parsing_config: KnowledgeParsingConfig | None = Field(
        default=None, description="The default parsing config."
    )


class KnowledgeBaseCreate(KnowledgeBaseBase):
    pass


class KnowledgeBasePut(KnowledgeBaseBase):
    pass


class KnowledgeBasePatch(BaseModel):
    name: str | None = Field(default=None, description="The name of the knowledge_base.")
    status: KnowledgeBaseStatus | None = Field(default=None, description="The status of the knowledge_base.")
    embedding_config: KnowledgeEmbeddingConfig | None = Field(default=None, description="The embedding config.")
    default_chunking_config: ChunkingConfig | None = Field(default=None, description="The default chunking config.")
    default_parsing_config: KnowledgeParsingConfig | None = Field(
        default=None, description="The default parsing config."
    )
    apply_mode: KnowledgeBaseConfigApplyMode = Field(
        default=KnowledgeBaseConfigApplyMode.INHERITED_ONLY,
        description="How config changes are applied to existing documents.",
    )


class KnowledgeBaseRead(UUIDSchemaMixin, TimestampSchemaMixin, KnowledgeBaseBase):
    status: KnowledgeBaseStatus = Field(description="Current status of the knowledge base.")
    embed_config_hash: str | None = Field(default=None, description="Hash signature of the embedding config.")
    model_config = ConfigDict(from_attributes=True)
