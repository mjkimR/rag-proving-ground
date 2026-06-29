from rag_core.adapters.prompt.providers.langfuse import LangfusePromptProvider
from rag_core.adapters.prompt.providers.s3 import S3PromptProvider
from rag_core.adapters.prompt.registry import PromptProviderRegistry


def register_default_prompt_providers() -> None:
    for provider in [S3PromptProvider, LangfusePromptProvider]:
        if provider.name not in PromptProviderRegistry.list_providers():
            PromptProviderRegistry.register(provider)


__all__ = ["LangfusePromptProvider", "S3PromptProvider", "register_default_prompt_providers"]
