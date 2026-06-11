from typing import Any

from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field


class DocumentParserBase(BaseModel):
    name: str = Field(description="The name of the document_parser.")
    is_active: bool = Field(default=True, description="Whether the parser is active")
    is_default: bool = Field(default=False, description="Whether this is the default parser")
    connection_info: dict[str, Any] | None = Field(default=None, description="Connection parameters")
    extra_metadata: dict[str, Any] | None = Field(default=None, description="Additional metadata")


class DocumentParserCreate(DocumentParserBase):
    pass


class DocumentParserPut(DocumentParserBase):
    pass


class DocumentParserPatch(BaseModel):
    name: str | None = Field(default=None, description="The name of the document_parser.")
    is_active: bool | None = Field(default=None, description="Whether the parser is active")
    is_default: bool | None = Field(default=None, description="Whether this is the default parser")
    connection_info: dict[str, Any] | None = Field(default=None, description="Connection parameters")
    extra_metadata: dict[str, Any] | None = Field(default=None, description="Additional metadata")


class DocumentParserRead(UUIDSchemaMixin, TimestampSchemaMixin, DocumentParserBase):
    model_config = ConfigDict(from_attributes=True)
