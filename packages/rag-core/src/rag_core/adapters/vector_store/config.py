import functools
from enum import StrEnum

from pydantic import Field
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


@functools.lru_cache
def get_vector_db_settings() -> VectorDBSettings:
    return VectorDBSettings()
