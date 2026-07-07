from app_layer_base.base.usecases.base import BaseUseCase
from rag_core.adapters.prompt.config import get_prompt_settings
from rag_core.adapters.prompt.registry import PromptProviderRegistry

from app.features.providers.prompts.schemas import PromptProviderInfo


class GetPromptProviderInfoUseCase(BaseUseCase):
    async def execute(self) -> PromptProviderInfo:
        settings = get_prompt_settings()
        providers = PromptProviderRegistry.list_providers()
        return PromptProviderInfo(
            current_provider=settings.provider,
            available_providers=providers,
            s3_bucket=settings.s3_bucket,
            fallback_dir=str(settings.fallback_dir) if settings.fallback_dir else None,
            langfuse_host=settings.langfuse_host,
        )
