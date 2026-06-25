from typing import Any
from cachetools import TTLCache, cached
from loguru import logger

from rag_core.adapters.prompt.factory import PromptFactory
from rag_core.adapters.prompt.interface import PromptProvider
from rag_core.adapters.prompt.config import get_prompt_settings


# Global cache for providers to avoid re-instantiating connections/clients
_provider_instance: PromptProvider | None = None

# Using TTLCache for actual prompt results.
# The ttl will be fetched dynamically from config on module load, but cachetools requires
# it at decorator setup time, so we fetch it once here.
_settings = get_prompt_settings()
_prompt_cache = TTLCache(maxsize=100, ttl=_settings.cache_ttl_seconds)


def get_prompt_provider() -> PromptProvider:
    """Returns a singleton instance of the configured prompt provider."""
    global _provider_instance
    if _provider_instance is None:
        settings = get_prompt_settings()
        _provider_instance = PromptFactory.create_provider(settings.provider)
        logger.info(f"Initialized prompt provider: {settings.provider}")
    return _provider_instance


@cached(cache=_prompt_cache)
def get_prompt(name: str, version: str | int | None = None) -> Any:
    """
    Retrieves a prompt template by name using the configured prompt provider.
    Results are cached based on the PROMPT_CACHE_TTL_SECONDS configuration.

    Args:
        name: Name/ID of the prompt to retrieve
        version: Specific version to retrieve. If None, retrieves the latest active version.

    Returns:
        The prompt template (can be string, dict, or Langfuse prompt object).
    """
    provider = get_prompt_provider()
    return provider.get_prompt(name, version=version)

def invalidate_prompt_cache() -> None:
    """Clears the prompt template cache."""
    _prompt_cache.clear()
