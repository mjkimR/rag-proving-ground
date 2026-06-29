from rag_core.adapters.prompt.interface import PromptProvider
from rag_core.adapters.prompt.providers import register_default_prompt_providers
from rag_core.adapters.prompt.registry import PromptProviderRegistry


class PromptFactory:
    """Factory facade for prompt provider creation."""

    @classmethod
    def create_provider(cls, provider: str) -> PromptProvider:
        register_default_prompt_providers()
        return PromptProviderRegistry.create_provider(provider)
