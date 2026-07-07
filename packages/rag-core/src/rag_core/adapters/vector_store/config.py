import functools
from enum import StrEnum

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class VectorDBProviderType(StrEnum):
    NONE = "none"
    QDRANT = "qdrant"
    MILVUS = "milvus"


class VectorDBSettings(BaseSettings):
    provider: VectorDBProviderType = Field(
        default=VectorDBProviderType.QDRANT,
        alias="VECTOR_DB_PROVIDER",
        description="Vector database backend to use: none | qdrant | milvus",
    )
    model_config = SettingsConfigDict(
        extra="ignore",
    )


class QdrantSettings(BaseSettings):
    url: str = Field(default="http://localhost:6333", description="Qdrant server URL")
    api_key: SecretStr | None = Field(default=None, description="API key for Qdrant authentication")
    model_config = SettingsConfigDict(env_prefix="VECTOR_DB_QDRANT_")


@functools.lru_cache
def get_vector_db_settings() -> VectorDBSettings:
    return VectorDBSettings()


@functools.lru_cache
def get_qdrant_settings() -> QdrantSettings:
    return QdrantSettings()  # type: ignore[call-arg]
