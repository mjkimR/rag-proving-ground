from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field


class FileAttachmentBase(BaseModel):
    sha256: str = Field(description="The SHA-256 hash of the file content.")
    filename: str = Field(description="The original filename of the uploaded file.")
    mime_type: str = Field(description="The MIME type of the file.")
    size_bytes: int = Field(description="The size of the file in bytes.")
    storage_path: str = Field(description="The storage path of the raw file.")


class FileAttachmentCreate(FileAttachmentBase):
    pass


class FileAttachmentPut(FileAttachmentBase):
    pass


class FileAttachmentPatch(BaseModel):
    filename: str | None = Field(default=None, description="The original filename of the uploaded file.")
    mime_type: str | None = Field(default=None, description="The MIME type of the file.")
    size_bytes: int | None = Field(default=None, description="The size of the file in bytes.")
    storage_path: str | None = Field(default=None, description="The storage path of the raw file.")


class FileAttachmentRead(UUIDSchemaMixin, TimestampSchemaMixin, FileAttachmentBase):
    model_config = ConfigDict(from_attributes=True)
