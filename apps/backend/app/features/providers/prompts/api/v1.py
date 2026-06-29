from typing import Annotated

from app.features.providers.prompts.schemas import (
    FallbackTemplateInfo,
    InvalidateCacheResponse,
    PromptProviderInfo,
)
from app.features.providers.prompts.usecases.get_info import GetPromptProviderInfoUseCase
from app.features.providers.prompts.usecases.invalidate import InvalidatePromptCacheUseCase
from app.features.providers.prompts.usecases.list_templates import ListFallbackTemplatesUseCase
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/providers/prompts", tags=["Providers: Prompts"])


@router.get("", response_model=PromptProviderInfo)
async def get_prompt_provider_info(
    use_case: Annotated[GetPromptProviderInfoUseCase, Depends()],
):
    return await use_case.execute()


@router.post("/cache/invalidate", response_model=InvalidateCacheResponse)
async def invalidate_cache(
    use_case: Annotated[InvalidatePromptCacheUseCase, Depends()],
):
    return await use_case.execute()


@router.get("/templates", response_model=list[FallbackTemplateInfo])
async def list_fallback_templates(
    use_case: Annotated[ListFallbackTemplatesUseCase, Depends()],
):
    return await use_case.execute()
