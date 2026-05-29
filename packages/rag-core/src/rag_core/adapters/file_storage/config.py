import functools
from enum import StrEnum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FileProviderType(StrEnum):
    NONE = "none"
    LOCAL = "local"
    S3 = "s3"


class FileStorageSettings(BaseSettings):
    """
    Main settings for file storage routing.
    Reads from environment variables.
    """

    provider: FileProviderType = Field(
        default=FileProviderType.NONE,
        alias="FS_PROVIDER",
        description="File storage backend to use: none | local | s3",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


@functools.lru_cache
def get_file_storage_settings() -> FileStorageSettings:
    """Returns a cached instance of the file storage routing settings."""
    return FileStorageSettings()
