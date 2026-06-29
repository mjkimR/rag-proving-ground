from fastapi import APIRouter
from rag_core.adapters.prompt.config import get_prompt_settings
from rag_core.adapters.prompt.registry import PromptProviderRegistry
from pydantic import BaseModel

router = APIRouter(prefix="/providers/prompts", tags=["Providers: Prompts"])

class PromptProviderInfo(BaseModel):
    current_provider: str
    available_providers: list[str]
    s3_bucket: str | None = None
    fallback_dir: str | None = None
    langfuse_host: str | None = None

@router.get("", response_model=PromptProviderInfo)
async def get_prompt_provider_info():
    settings = get_prompt_settings()
    providers = PromptProviderRegistry.list_providers()
    return PromptProviderInfo(
        current_provider=settings.provider,
        available_providers=providers,
        s3_bucket=settings.s3_bucket,
        fallback_dir=settings.fallback_dir,
        langfuse_host=settings.langfuse_host,
    )
