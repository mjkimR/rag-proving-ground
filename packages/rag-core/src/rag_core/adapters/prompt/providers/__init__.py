from rag_core.adapters.prompt.providers.s3 import S3PromptProvider
from rag_core.adapters.prompt.providers.langfuse import LangfusePromptProvider
from rag_core.adapters.prompt.registry import PromptProviderRegistry

def register_default_prompt_providers() -> None:
    for provider in [S3PromptProvider, LangfusePromptProvider]:
        try:
            PromptProviderRegistry.register(provider)
        except ValueError:
            pass

__all__ = ["register_default_prompt_providers", "S3PromptProvider", "LangfusePromptProvider"]
