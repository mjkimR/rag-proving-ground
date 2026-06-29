from pydantic import BaseModel


class PromptProviderInfo(BaseModel):
    current_provider: str
    available_providers: list[str]
    s3_bucket: str | None = None
    fallback_dir: str | None = None
    langfuse_host: str | None = None


class InvalidateCacheResponse(BaseModel):
    success: bool
    message: str


class FallbackTemplateInfo(BaseModel):
    name: str
    format: str
    content: str
