"""LangChain model factories for the LiteLLM gateway."""

import json
import logging
from typing import Any

from langchain_core.documents import BaseDocumentCompressor
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_litellm import ChatLiteLLM, LiteLLMEmbeddings

from rag_core.ai.reranker import LiteLLMRerankCompressor
from rag_core.config import get_litellm_settings

logger = logging.getLogger(__name__)

_LLM_MODEL_CACHE: dict[str, BaseChatModel] = {}
_EMBEDDING_MODEL_CACHE: dict[str, Embeddings] = {}
_RERANKER_MODEL_CACHE: dict[str, BaseDocumentCompressor] = {}


def get_llm_model(model_name: str | None = None, **kwargs: Any) -> BaseChatModel | Runnable:
    settings = get_litellm_settings()
    model = _gateway_openai_model(model_name or settings.default_llm_model)
    bind_kwargs = dict(kwargs)
    model_kwargs = {
        "model": model,
        "api_base": settings.base_url,
        "temperature": bind_kwargs.pop("temperature", settings.temperature),
        "max_tokens": bind_kwargs.pop("max_tokens", settings.max_tokens),
        "request_timeout": bind_kwargs.pop("request_timeout", settings.timeout),
        "max_retries": bind_kwargs.pop("max_retries", settings.max_retries),
    }
    cache_key = _json_cache_key(model_kwargs)
    if cache_key not in _LLM_MODEL_CACHE:
        _LLM_MODEL_CACHE[cache_key] = ChatLiteLLM(
            **model_kwargs,
            api_key=settings.api_key.get_secret_value(),
        )
    cached_model = _LLM_MODEL_CACHE[cache_key]
    if not bind_kwargs:
        return cached_model
    return cached_model.bind(**bind_kwargs)


def get_embedding_model(model_name: str | None = None, **kwargs: Any) -> Embeddings:
    settings = get_litellm_settings()
    model = _gateway_openai_model(model_name or settings.default_embedding_model)
    model_kwargs = dict(kwargs)
    constructor_kwargs = {
        "model": model,
        "api_base": settings.base_url,
        "request_timeout": model_kwargs.pop("request_timeout", settings.timeout),
        "max_retries": model_kwargs.pop("max_retries", settings.max_retries),
        **model_kwargs,
    }
    cache_key = _json_cache_key(constructor_kwargs)
    if cache_key not in _EMBEDDING_MODEL_CACHE:
        _EMBEDDING_MODEL_CACHE[cache_key] = LiteLLMEmbeddings(
            **constructor_kwargs,
            api_key=settings.api_key.get_secret_value(),
        )
    return _EMBEDDING_MODEL_CACHE[cache_key]


def get_reranker_model(model_name: str | None = None, **kwargs: Any) -> BaseDocumentCompressor:
    settings = get_litellm_settings()
    model_kwargs = dict(kwargs)
    constructor_kwargs = {
        "model": model_name or settings.default_reranker_model,
        "api_base": _gateway_base_url(settings.base_url),
        "request_timeout": model_kwargs.pop("request_timeout", settings.timeout),
        "max_retries": model_kwargs.pop("max_retries", settings.max_retries),
        **model_kwargs,
    }
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
