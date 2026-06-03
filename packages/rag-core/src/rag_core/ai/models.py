"""LangChain model factories for the LiteLLM gateway."""

import json
import logging
import os
from functools import lru_cache
from typing import Any

import yaml
from app_http_client import get_http_sync_client
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


@lru_cache(maxsize=1)
def get_model_options() -> dict[str, list[str]]:
    """Parse models from LiteLLM gateway API or fallback to models.yaml and return categorized lists."""
    settings = get_litellm_settings()
    info_url = f"{_gateway_base_url(settings.base_url)}/model/info"

    headers = {}
    if settings.api_key:
        headers["Authorization"] = f"Bearer {settings.api_key.get_secret_value()}"

    try:
        client = get_http_sync_client()
        response = client.get(info_url, headers=headers, timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            model_list = data
            if isinstance(data, dict) and "data" in data:
                model_list = data["data"]
            elif isinstance(data, dict) and "model_list" in data:
                model_list = data["model_list"]

            if isinstance(model_list, list):
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
                        if "embedding" in name_lower:
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

                logger.info("Successfully fetched model options dynamically from LiteLLM gateway.")
                return {
                    "embedding_models": embedding_models,
                    "llm_models": llm_models,
                    "reranker_models": reranker_models,
                }
    except Exception as e:
        logger.warning(
            f"Failed to fetch model info from LiteLLM gateway ({info_url}): {e}. Falling back to models.yaml."
        )

    yaml_path = os.environ.get("MODELS_YAML_PATH")
    if not yaml_path:
        search_paths = [
            "models.yaml",
            "../models.yaml",
            "../../models.yaml",
        ]
        for p in search_paths:
            if os.path.exists(p):
                yaml_path = p
                break

    if not yaml_path or not os.path.exists(yaml_path):
        logger.warning("models.yaml not found, returning fallback defaults")
        return {
            "embedding_models": ["vllm-embedding"],
            "llm_models": ["gpt-oss-20b"],
            "reranker_models": ["vllm-reranker"],
        }

    try:
        with open(yaml_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to parse models.yaml: {e}")
        return {
            "embedding_models": ["vllm-embedding"],
            "llm_models": ["gpt-oss-20b"],
            "reranker_models": ["vllm-reranker"],
        }

    model_list = config.get("model_list", []) or []
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
            if "embedding" in name_lower:
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
