"""LangChain model factories for the LiteLLM gateway."""

import json
import logging
from typing import Any

from langchain_core.documents import BaseDocumentCompressor
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_litellm import ChatLiteLLM, LiteLLMEmbeddings

from rag_core.ai.gateway import (
    _fetch_model_options_from_gateway,
    _fetch_raw_model_info_from_gateway,
    _gateway_base_url,
    _get_model_metadata_map,
    get_model_metadata,
    get_model_options,
)
from rag_core.ai.reranker import LiteLLMRerankCompressor
from rag_core.ai.sparse import SparseEmbeddings as SparseEmbeddings
from rag_core.ai.sparse import get_sparse_embedding_model as get_sparse_embedding_model
from rag_core.config import get_litellm_settings

__all__ = [
    "clear_gateway_cache",
    "get_embedding_model",
    "get_llm_model",
    "get_model_metadata",
    "get_model_options",
    "get_reranker_model",
    "update_model_registry",
]

logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)

# Standard parameters for model initialization and routing
TEMPERATURE = "temperature"
MAX_TOKENS = "max_tokens"
REQUEST_TIMEOUT = "request_timeout"
MAX_RETRIES = "max_retries"

LLM_STANDARD_PARAMS = (
    TEMPERATURE,
    MAX_TOKENS,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
)

SHARED_STANDARD_PARAMS = (
    REQUEST_TIMEOUT,
    MAX_RETRIES,
)

_LLM_MODEL_CACHE: dict[str, BaseChatModel] = {}
_EMBEDDING_MODEL_CACHE: dict[str, Embeddings] = {}
_RERANKER_MODEL_CACHE: dict[str, BaseDocumentCompressor] = {}

# Global registry for active models populated from the database
_ACTIVE_MODELS: dict[str, dict[str, Any]] = {}
_DEFAULT_MODELS: dict[str, dict[str, Any]] = {}


def update_model_registry(models: list[dict[str, Any]]) -> None:
    """Updates the in-memory active and default model configurations.

    Args:
        models: A list of model configuration dictionaries loaded from the database.
    """
    global _ACTIVE_MODELS, _DEFAULT_MODELS
    _ACTIVE_MODELS = {m["name"]: m for m in models if m.get("is_active", True)}
    _DEFAULT_MODELS = {}
    for m in models:
        if m.get("is_active", True) and m.get("is_default", False):
            _DEFAULT_MODELS[m["model_type"]] = m


def clear_gateway_cache() -> None:
    """Clears all lru_cache instances caching LiteLLM gateway dynamic model information."""
    _fetch_raw_model_info_from_gateway.cache_clear()
    _get_model_metadata_map.cache_clear()
    _fetch_model_options_from_gateway.cache_clear()


def _resolve_model_params(
    passed_kwargs: dict[str, Any],
    yaml_params: dict[str, Any],
    standard_keys: list[str] | tuple[str, ...],
    default_settings: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve and merge model parameters based on priority.

    Priority: passed_kwargs > yaml_params > default_settings

    Returns:
        tuple[resolved_params, remaining_kwargs]:
            - resolved_params: Merged standard parameters (if not None) and custom yaml_params.
            - remaining_kwargs: The passed kwargs with standard keys popped out.
    """
    remaining_kwargs = dict(passed_kwargs)
    resolved_params = {}

    # 1. Resolve standard parameters
    for key in standard_keys:
        if key in remaining_kwargs:
            val = remaining_kwargs.pop(key)
        else:
            val = yaml_params.get(key)
            if val is None:
                val = default_settings.get(key)

        if val is not None:
            resolved_params[key] = val

    # 2. Merge other custom yaml_params (excluding standard parameters)
    for k, v in yaml_params.items():
        if k not in standard_keys:
            resolved_params[k] = v

    return resolved_params, remaining_kwargs


def get_llm_model(model_name: str | None = None, **kwargs: Any) -> BaseChatModel | Runnable:
    """Retrieves an initialized ChatLiteLLM model or bind-wrapped Runnable from the cache.

    Integrates with the LiteLLM proxy gateway by utilizing settings retrieved from
    `get_litellm_settings()`. The request is routed to `settings.base_url` using the
    api key in `settings.api_key`.

    If no model_name is specified, falls back to the default LLM model from the database
    registry or application settings.

    Args:
        model_name: The name of the LLM model to retrieve.
        **kwargs: Standard parameters (e.g., temperature, max_tokens) or bind kwargs to override.

    Returns:
        BaseChatModel | Runnable: The cached LLM instance, potentially wrapped with bound arguments.
    """
    settings = get_litellm_settings()

    # 1. Resolve model name
    resolved_model_name = model_name
    if not resolved_model_name:
        default_model = _DEFAULT_MODELS.get("llm")
        resolved_model_name = default_model["name"] if default_model else settings.default_llm_model

    # 2. Get model params from database registry first, fall back to gateway metadata
    cached_model = _ACTIVE_MODELS.get(resolved_model_name)
    if cached_model:
        model_params = cached_model.get("metadata", {}).get("model_params") or {}
    else:
        metadata = get_model_metadata(resolved_model_name)
        model_params = metadata.get("model_params") or {}

    default_settings = {
        TEMPERATURE: settings.temperature,
        MAX_TOKENS: settings.max_tokens,
        REQUEST_TIMEOUT: settings.timeout,
        MAX_RETRIES: settings.max_retries,
    }

    resolved_params, bind_kwargs = _resolve_model_params(
        passed_kwargs=kwargs,
        yaml_params=model_params,
        standard_keys=LLM_STANDARD_PARAMS,
        default_settings=default_settings,
    )

    model = _gateway_openai_model(resolved_model_name)
    model_kwargs: dict[str, Any] = {
        "model": model,
        "api_base": settings.base_url,
        **resolved_params,
    }

    cache_key = _json_cache_key(model_kwargs)
    if cache_key not in _LLM_MODEL_CACHE:
        _LLM_MODEL_CACHE[cache_key] = ChatLiteLLM(
            **model_kwargs,
            api_key=settings.api_key.get_secret_value(),
            streaming=True,
        )
    cached_model_inst = _LLM_MODEL_CACHE[cache_key]
    if not bind_kwargs:
        return cached_model_inst
    return cached_model_inst.bind(**bind_kwargs)


def get_embedding_model(model_name: str | None = None, **kwargs: Any) -> Embeddings:
    """Retrieves an initialized LiteLLMEmbeddings instance from the cache.

    Integrates with the LiteLLM proxy gateway by utilizing settings retrieved from
    `get_litellm_settings()`. The embedding request is routed to `settings.base_url` using
    the api key in `settings.api_key`.

    If no model_name is specified, falls back to the default embedding model from the
    database registry or application settings.

    Args:
        model_name: The name of the embedding model to retrieve.
        **kwargs: Additional parameters (e.g., timeout, max_retries) to override.

    Returns:
        Embeddings: The cached LangChain Embeddings instance.
    """
    settings = get_litellm_settings()

    # 1. Resolve model name
    resolved_model_name = model_name
    if not resolved_model_name:
        default_model = _DEFAULT_MODELS.get("embedding")
        resolved_model_name = default_model["name"] if default_model else settings.default_embedding_model

    # 2. Get model params from database registry first, fall back to gateway metadata
    cached_model = _ACTIVE_MODELS.get(resolved_model_name)
    if cached_model:
        model_params = cached_model.get("metadata", {}).get("model_params") or {}
    else:
        metadata = get_model_metadata(resolved_model_name)
        model_params = metadata.get("model_params") or {}

    default_settings = {
        REQUEST_TIMEOUT: settings.timeout,
        MAX_RETRIES: settings.max_retries,
    }

    resolved_params, remaining_kwargs = _resolve_model_params(
        passed_kwargs=kwargs,
        yaml_params=model_params,
        standard_keys=SHARED_STANDARD_PARAMS,
        default_settings=default_settings,
    )

    model = _gateway_openai_model(resolved_model_name)
    constructor_kwargs: dict[str, Any] = {
        "model": model,
        "api_base": settings.base_url,
        **resolved_params,
    }
    constructor_kwargs.update(remaining_kwargs)

    cache_key = _json_cache_key(constructor_kwargs)
    if cache_key not in _EMBEDDING_MODEL_CACHE:
        _EMBEDDING_MODEL_CACHE[cache_key] = LiteLLMEmbeddings(
            **constructor_kwargs,
            api_key=settings.api_key.get_secret_value(),
        )
    return _EMBEDDING_MODEL_CACHE[cache_key]


def get_reranker_model(model_name: str | None = None, **kwargs: Any) -> BaseDocumentCompressor:
    """Retrieves an initialized LiteLLMRerankCompressor instance from the cache.

    Integrates with the LiteLLM proxy gateway by utilizing settings retrieved from
    `get_litellm_settings()`. The reranking request is routed to `settings.base_url` using
    the api key in `settings.api_key`.

    If no model_name is specified, falls back to the default reranker model from the
    database registry or application settings.

    Args:
        model_name: The name of the reranker model to retrieve.
        **kwargs: Additional parameters (e.g., top_n, timeout, max_retries) to override.

    Returns:
        BaseDocumentCompressor: The cached LiteLLMRerankCompressor instance.
    """
    settings = get_litellm_settings()

    # 1. Resolve model name
    resolved_model_name = model_name
    if not resolved_model_name:
        default_model = _DEFAULT_MODELS.get("reranker")
        resolved_model_name = default_model["name"] if default_model else settings.default_reranker_model

    # 2. Get model params from database registry first, fall back to gateway metadata
    cached_model = _ACTIVE_MODELS.get(resolved_model_name)
    if cached_model:
        model_params = cached_model.get("metadata", {}).get("model_params") or {}
    else:
        metadata = get_model_metadata(resolved_model_name)
        model_params = metadata.get("model_params") or {}

    default_settings = {
        REQUEST_TIMEOUT: settings.timeout,
        MAX_RETRIES: settings.max_retries,
    }

    resolved_params, remaining_kwargs = _resolve_model_params(
        passed_kwargs=kwargs,
        yaml_params=model_params,
        standard_keys=SHARED_STANDARD_PARAMS,
        default_settings=default_settings,
    )

    constructor_kwargs: dict[str, Any] = {
        "model": resolved_model_name,
        "api_base": _gateway_base_url(settings.base_url),
        **resolved_params,
    }
    constructor_kwargs.update(remaining_kwargs)

    cache_key = _json_cache_key(constructor_kwargs)
    if cache_key not in _RERANKER_MODEL_CACHE:
        _RERANKER_MODEL_CACHE[cache_key] = LiteLLMRerankCompressor(
            **constructor_kwargs,
            api_key=settings.api_key,
        )
    return _RERANKER_MODEL_CACHE[cache_key]


def _gateway_openai_model(model_name: str) -> str:
    if "/" in model_name:
        return model_name
    return f"openai/{model_name}"


def _json_cache_key(value: Any) -> str:
    return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"))


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {_json_safe_key(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value

    logger.warning(
        f"Non-JSON-serializable value used in model cache key; falling back to "
        f"str(). type={type(value).__qualname__} value={value!r}"
    )
    return str(value)


def _json_safe_key(value: Any) -> str:
    if not isinstance(value, str):
        logger.warning(
            f"Non-string mapping key used in model cache key; falling back to "
            f"str(). type={type(value).__qualname__} value={value!r}"
        )
    return str(value)
