from typing import Any

from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field


class AIModelBase(BaseModel):
    name: str = Field(description="The name of the ai_model.")
    provider: str = Field(description="The provider of the model (e.g. openai, gemini, etc.)")
    model_type: str = Field(description="The type of the model (llm, embedding, reranker)")
    is_active: bool = Field(default=True, description="Whether the model is active")
    is_default: bool = Field(default=False, description="Whether this is the default model for its type")
    connection_info: dict[str, Any] | None = Field(default=None, description="Connection parameters")
    extra_metadata: dict[str, Any] | None = Field(default=None, description="Additional metadata")


class AIModelCreate(AIModelBase):
    pass


class AIModelPut(AIModelBase):
    pass


class AIModelPatch(BaseModel):
    name: str | None = Field(default=None, description="The name of the ai_model.")
    provider: str | None = Field(default=None, description="The provider of the model.")
    model_type: str | None = Field(default=None, description="The type of the model.")
    is_active: bool | None = Field(default=None, description="Whether the model is active")
    is_default: bool | None = Field(default=None, description="Whether this is the default model")
    connection_info: dict[str, Any] | None = Field(default=None, description="Connection parameters")
    extra_metadata: dict[str, Any] | None = Field(default=None, description="Additional metadata")


class AIModelRead(UUIDSchemaMixin, TimestampSchemaMixin, AIModelBase):
    model_config = ConfigDict(from_attributes=True)
