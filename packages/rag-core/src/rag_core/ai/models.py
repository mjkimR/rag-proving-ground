"""LangChain model factories for the LiteLLM gateway."""

import json
import logging
from functools import lru_cache
from typing import Any

from app_http_client import get_http_sync_client
from langchain_core.documents import BaseDocumentCompressor
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_litellm import ChatLiteLLM, LiteLLMEmbeddings

from rag_core.ai.reranker import LiteLLMRerankCompressor
from rag_core.ai.sparse import SparseEmbeddings as SparseEmbeddings
from rag_core.ai.sparse import get_sparse_embedding_model as get_sparse_embedding_model
from rag_core.config import get_litellm_settings

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
    """Update the in-memory active and default model registry."""
    global _ACTIVE_MODELS, _DEFAULT_MODELS
    _ACTIVE_MODELS = {m["name"]: m for m in models if m.get("is_active", True)}
    _DEFAULT_MODELS = {}
    for m in models:
        if m.get("is_active", True) and m.get("is_default", False):
            _DEFAULT_MODELS[m["model_type"]] = m


def clear_gateway_cache() -> None:
    """Clear the lru_cache for LiteLLM gateway information."""
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
    settings = get_litellm_settings()

    # 1. Resolve model name
    resolved_model_name = model_name
    if not resolved_model_name:
        default_model = _DEFAULT_MODELS.get("llm")
        resolved_model_name = default_model["name"] if default_model else settings.default_llm_model

    # 2. Check registry
    cached_model = _ACTIVE_MODELS.get(resolved_model_name)
    if cached_model:
        connection_info = cached_model.get("connection_info") or {}
        model = connection_info.get("model") or _gateway_openai_model(resolved_model_name)
        api_base = connection_info.get("api_base") or settings.base_url
        api_key_val = connection_info.get("api_key")

        default_settings = {
            TEMPERATURE: settings.temperature,
            MAX_TOKENS: settings.max_tokens,
            REQUEST_TIMEOUT: settings.timeout,
            MAX_RETRIES: settings.max_retries,
        }

        # Merge parameters from metadata and connection_info
        model_params = dict(cached_model.get("metadata", {}).get("model_params") or {})
        model_params.update({k: v for k, v in connection_info.items() if k in LLM_STANDARD_PARAMS})

        resolved_params, bind_kwargs = _resolve_model_params(
            passed_kwargs=kwargs,
            yaml_params=model_params,
            standard_keys=LLM_STANDARD_PARAMS,
            default_settings=default_settings,
        )

        model_kwargs: dict[str, Any] = {
            "model": model,
            "api_base": api_base,
            **resolved_params,
        }

        cache_key = _json_cache_key(model_kwargs)
        if cache_key not in _LLM_MODEL_CACHE:
            api_key = api_key_val
            if not api_key:
                api_key = settings.api_key.get_secret_value() if settings.api_key else None

            _LLM_MODEL_CACHE[cache_key] = ChatLiteLLM(
                **model_kwargs,
                api_key=api_key,
                streaming=True,
            )
        cached_model_inst = _LLM_MODEL_CACHE[cache_key]
        if not bind_kwargs:
            return cached_model_inst
        return cached_model_inst.bind(**bind_kwargs)

    # 3. Fallback to gateway defaults
    model = _gateway_openai_model(resolved_model_name)
    metadata = get_model_metadata(resolved_model_name)
    yaml_model_params = metadata.get("model_params") or {}

    default_settings = {
        TEMPERATURE: settings.temperature,
        MAX_TOKENS: settings.max_tokens,
        REQUEST_TIMEOUT: settings.timeout,
        MAX_RETRIES: settings.max_retries,
    }

    resolved_params, bind_kwargs = _resolve_model_params(
        passed_kwargs=kwargs,
        yaml_params=yaml_model_params,
        standard_keys=LLM_STANDARD_PARAMS,
        default_settings=default_settings,
    )

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
    settings = get_litellm_settings()

    # 1. Resolve model name
    resolved_model_name = model_name
    if not resolved_model_name:
        default_model = _DEFAULT_MODELS.get("embedding")
        resolved_model_name = default_model["name"] if default_model else settings.default_embedding_model

    # 2. Check registry
    cached_model = _ACTIVE_MODELS.get(resolved_model_name)
    if cached_model:
        connection_info = cached_model.get("connection_info") or {}
        model = connection_info.get("model") or _gateway_openai_model(resolved_model_name)
        api_base = connection_info.get("api_base") or settings.base_url
        api_key_val = connection_info.get("api_key")

        default_settings = {
            REQUEST_TIMEOUT: settings.timeout,
            MAX_RETRIES: settings.max_retries,
        }

        model_params = dict(cached_model.get("metadata", {}).get("model_params") or {})
        model_params.update({k: v for k, v in connection_info.items() if k in SHARED_STANDARD_PARAMS})

        resolved_params, remaining_kwargs = _resolve_model_params(
            passed_kwargs=kwargs,
            yaml_params=model_params,
            standard_keys=SHARED_STANDARD_PARAMS,
            default_settings=default_settings,
        )

        constructor_kwargs: dict[str, Any] = {
            "model": model,
            "api_base": api_base,
            **resolved_params,
        }
        constructor_kwargs.update(remaining_kwargs)

        cache_key = _json_cache_key(constructor_kwargs)
        if cache_key not in _EMBEDDING_MODEL_CACHE:
            api_key = api_key_val
            if not api_key:
                api_key = settings.api_key.get_secret_value() if settings.api_key else None

            _EMBEDDING_MODEL_CACHE[cache_key] = LiteLLMEmbeddings(
                **constructor_kwargs,
                api_key=api_key,
            )
        return _EMBEDDING_MODEL_CACHE[cache_key]

    # 3. Fallback
    model = _gateway_openai_model(resolved_model_name)
    metadata = get_model_metadata(resolved_model_name)
    yaml_model_params = metadata.get("model_params") or {}

    default_settings = {
        REQUEST_TIMEOUT: settings.timeout,
        MAX_RETRIES: settings.max_retries,
    }

    resolved_params, remaining_kwargs = _resolve_model_params(
        passed_kwargs=kwargs,
        yaml_params=yaml_model_params,
        standard_keys=SHARED_STANDARD_PARAMS,
        default_settings=default_settings,
    )

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
    settings = get_litellm_settings()

    # 1. Resolve model name
    resolved_model_name = model_name
    if not resolved_model_name:
        default_model = _DEFAULT_MODELS.get("reranker")
        resolved_model_name = default_model["name"] if default_model else settings.default_reranker_model

    # 2. Check registry
    cached_model = _ACTIVE_MODELS.get(resolved_model_name)
    if cached_model:
        connection_info = cached_model.get("connection_info") or {}
        model = connection_info.get("model") or resolved_model_name
        api_base = connection_info.get("api_base") or _gateway_base_url(settings.base_url)
        api_key_val = connection_info.get("api_key")

        default_settings = {
            REQUEST_TIMEOUT: settings.timeout,
            MAX_RETRIES: settings.max_retries,
        }

        model_params = dict(cached_model.get("metadata", {}).get("model_params") or {})
        model_params.update({k: v for k, v in connection_info.items() if k in SHARED_STANDARD_PARAMS})

        resolved_params, remaining_kwargs = _resolve_model_params(
            passed_kwargs=kwargs,
            yaml_params=model_params,
            standard_keys=SHARED_STANDARD_PARAMS,
            default_settings=default_settings,
        )

        constructor_kwargs: dict[str, Any] = {
            "model": model,
            "api_base": api_base,
            **resolved_params,
        }
        constructor_kwargs.update(remaining_kwargs)

        cache_key = _json_cache_key(constructor_kwargs)
        if cache_key not in _RERANKER_MODEL_CACHE:
            _RERANKER_MODEL_CACHE[cache_key] = LiteLLMRerankCompressor(
                **constructor_kwargs,
                api_key=api_key_val or settings.api_key,
            )
        return _RERANKER_MODEL_CACHE[cache_key]

    # 3. Fallback
    metadata = get_model_metadata(resolved_model_name)
    yaml_model_params = metadata.get("model_params") or {}

    default_settings = {
        REQUEST_TIMEOUT: settings.timeout,
        MAX_RETRIES: settings.max_retries,
    }

    resolved_params, remaining_kwargs = _resolve_model_params(
        passed_kwargs=kwargs,
        yaml_params=yaml_model_params,
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


def _gateway_base_url(base_url: str) -> str:
    return base_url.removesuffix("/v1").rstrip("/")


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


@lru_cache(maxsize=1)
def _fetch_raw_model_info_from_gateway() -> list[dict[str, Any]]:
    """Fetch raw model list from LiteLLM gateway.

    Raises:
        Exception: If the fetch or parsing fails, ensuring failures are not cached.
    """
    settings = get_litellm_settings()
    info_url = f"{_gateway_base_url(settings.base_url)}/model/info"

    headers = {}
    if settings.api_key:
        headers["Authorization"] = f"Bearer {settings.api_key.get_secret_value()}"

    client = get_http_sync_client()
    response = client.get(info_url, headers=headers, timeout=5.0)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch model info from LiteLLM gateway. Status code: {response.status_code}")

    data = response.json()
    model_list = data
    if isinstance(data, dict) and "data" in data:
        model_list = data["data"]
    elif isinstance(data, dict) and "model_list" in data:
        model_list = data["model_list"]

    if not isinstance(model_list, list):
        raise ValueError(f"Unexpected model list format from LiteLLM gateway: {type(model_list).__name__}")

    logger.info("Successfully fetched model options dynamically from LiteLLM gateway.")
    return model_list


@lru_cache(maxsize=1)
def _get_model_metadata_map() -> dict[str, dict[str, Any]]:
    """Build a mapping of model name to metadata from fetched gateway info.

    Raises:
        Exception: If the fetch or parsing fails, ensuring failures are not cached.
    """
    model_list = _fetch_raw_model_info_from_gateway()
    return {entry["model_name"]: entry.get("metadata") or {} for entry in model_list if "model_name" in entry}


def get_model_metadata(model_name: str) -> dict[str, Any]:
    """Get metadata for a specific model from cached gateway info."""
    try:
        metadata_map = _get_model_metadata_map()
        return metadata_map.get(model_name) or {}
    except Exception as e:
        logger.warning(f"Failed to get metadata for model {model_name}: {e}")
    return {}


@lru_cache(maxsize=1)
def _fetch_model_options_from_gateway() -> dict[str, list[str]]:
    """Fetch model options from the LiteLLM gateway API.

    Raises:
        Exception: If the fetch or parsing fails, ensuring failures are not cached.
    """
    model_list = _fetch_raw_model_info_from_gateway()

    embedding_models = []
    llm_models = []
    reranker_models = []

    for entry in model_list:
        name = entry.get("model_name")
        if not name:
            continue

        metadata = entry.get("metadata") or {}
        role = metadata.get("role") or metadata.get("type")

        if not role and "tags" in metadata:
            tags = metadata.get("tags") or []
            if "embedding" in tags:
                role = "embedding"
            elif "reranker" in tags:
                role = "reranker"
            elif "llm" in tags or "chat" in tags:
                role = "llm"

        if not role:
            # Name heuristics
            name_lower = name.lower()
            if "embedding" in name_lower or ("bge" in name_lower and "rerank" not in name_lower):
                role = "embedding"
            elif "reranker" in name_lower or "rerank" in name_lower:
                role = "reranker"
            else:
                role = "llm"

        if role == "embedding":
            embedding_models.append(name)
        elif role == "reranker":
            reranker_models.append(name)
        else:
            llm_models.append(name)

    return {
        "embedding_models": embedding_models,
        "llm_models": llm_models,
        "reranker_models": reranker_models,
    }


def get_model_options() -> dict[str, list[str]]:
    """Retrieve categorized list of available models from the LiteLLM gateway.

    If the fetch fails, it returns a fallback placeholder dictionary to ensure
    downstream compatibility without caching the failure.
    """
    try:
        return _fetch_model_options_from_gateway()
    except Exception as e:
        settings = get_litellm_settings()
        info_url = f"{_gateway_base_url(settings.base_url)}/model/info"
        logger.warning(
            f"Failed to fetch model info from LiteLLM gateway ({info_url}): {e}. "
            f"Returning fallback 'no-model' placeholders."
        )
        return {
            "embedding_models": ["no-model"],
            "llm_models": ["no-model"],
            "reranker_models": ["no-model"],
        }
