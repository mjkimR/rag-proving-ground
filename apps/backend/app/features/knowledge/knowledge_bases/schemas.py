from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBaseBase(BaseModel):
    name: str = Field(description="The name of the knowledge_base.")
    embedding_config: dict | None = Field(default=None, description="The embedding config.")
    default_chunking_config: dict | None = Field(default=None, description="The default chunking config.")
    default_parsing_config: dict | None = Field(default=None, description="The default parsing config.")


class KnowledgeBaseCreate(KnowledgeBaseBase):
    pass


class KnowledgeBasePut(KnowledgeBaseBase):
    pass


class KnowledgeBasePatch(BaseModel):
    name: str | None = Field(default=None, description="The name of the knowledge_base.")
    status: str | None = Field(default=None, description="The status of the knowledge_base.")
    embedding_config: dict | None = Field(default=None, description="The embedding config.")
    default_chunking_config: dict | None = Field(default=None, description="The default chunking config.")
    default_parsing_config: dict | None = Field(default=None, description="The default parsing config.")


class KnowledgeBaseRead(UUIDSchemaMixin, TimestampSchemaMixin, KnowledgeBaseBase):
    status: str = Field(description="Current status of the knowledge base.")
    embed_config_hash: str | None = Field(default=None, description="Hash signature of the embedding config.")
    model_config = ConfigDict(from_attributes=True)
