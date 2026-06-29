from typing import ClassVar

from rag_core.adapters.prompt.interface import PromptProvider


class PromptProviderRegistry:
    """Registry for prompt providers keyed by provider name."""

    _providers: ClassVar[dict[str, type[PromptProvider]]] = {}

    @classmethod
    def register(cls, provider_class: type[PromptProvider]) -> None:
        provider_name = provider_class.name
        if provider_name in cls._providers:
            raise ValueError(f"Prompt Provider is already registered: {provider_name}")

        cls._providers[provider_name] = provider_class

    @classmethod
    def get_provider_class(cls, provider_name: str) -> type[PromptProvider]:
        try:
            return cls._providers[provider_name]
        except KeyError as exc:
            raise ValueError(f"Unsupported prompt provider: {provider_name}") from exc

    @classmethod
    def create_provider(cls, provider: str) -> PromptProvider:
        provider_class = cls.get_provider_class(provider)
        return provider_class.from_config()

    @classmethod
    def list_providers(cls) -> list[str]:
        return sorted(cls._providers)
