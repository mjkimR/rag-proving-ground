from app_layer_base.base.usecases.base import BaseUseCase
from rag_core.adapters.prompt.instance import invalidate_prompt_cache

from app.features.providers.prompts.schemas import InvalidateCacheResponse


class InvalidatePromptCacheUseCase(BaseUseCase):
    async def execute(self) -> InvalidateCacheResponse:
        invalidate_prompt_cache()
        return InvalidateCacheResponse(success=True, message="Prompt cache has been invalidated.")
