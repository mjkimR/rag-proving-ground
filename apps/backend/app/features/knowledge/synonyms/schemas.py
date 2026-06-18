from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field


class SynonymMapBase(BaseModel):
    keyword: str = Field(
        ..., min_length=1, max_length=255, description="The trigger keyword or abbreviation (e.g. RAG)."
    )
    synonyms: list[str] = Field(..., min_length=1, description="List of synonyms to map to this keyword.")
    description: str | None = Field(default=None, description="Optional description of this synonym mapping.")


class SynonymMapCreate(SynonymMapBase):
    pass


class SynonymMapPut(SynonymMapBase):
    pass


class SynonymMapPatch(BaseModel):
    keyword: str | None = Field(
        default=None, min_length=1, max_length=255, description="The trigger keyword or abbreviation."
    )
    synonyms: list[str] | None = Field(
        default=None, min_length=1, description="List of synonyms to map to this keyword."
    )
    description: str | None = Field(default=None, description="Optional description of this synonym mapping.")


class SynonymMapRead(UUIDSchemaMixin, TimestampSchemaMixin, SynonymMapBase):
    model_config = ConfigDict(from_attributes=True)
