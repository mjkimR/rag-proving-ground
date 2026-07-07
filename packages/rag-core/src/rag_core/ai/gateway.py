"""LiteLLM gateway interaction and dynamic model discovery/metadata caching."""

import logging
from functools import lru_cache
from typing import Any

from app_http_client import get_http_sync_client

from rag_core.config import get_litellm_settings

logger = logging.getLogger(__name__)


def _gateway_base_url(base_url: str) -> str:
    """Returns the LiteLLM gateway base URL without trailing slashes and '/v1' suffixes.

    Args:
        base_url: The raw gateway API base URL.

    Returns:
        str: The normalized base URL.
    """
    return base_url.removesuffix("/v1").rstrip("/")


@lru_cache(maxsize=1)
def fetch_raw_model_info_from_gateway() -> list[dict[str, Any]]:
    """Fetches the raw model list from the LiteLLM gateway.

    Retrieves model metadata from the LiteLLM gateway using settings.base_url and
    settings.api_key.

    Raises:
        RuntimeError: If the fetch request fails.
        ValueError: If the model list format returned from the gateway is invalid.
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
    """Builds a mapping of model name to metadata from fetched gateway info.

    Returns:
        dict[str, dict[str, Any]]: A mapping of model name to its metadata.
    """
    model_list = fetch_raw_model_info_from_gateway()
    return {entry["model_name"]: entry.get("metadata") or {} for entry in model_list if "model_name" in entry}


def get_model_metadata(model_name: str) -> dict[str, Any]:
    """Retrieves metadata for a specific model from the cached LiteLLM gateway info.

    Args:
        model_name: The name of the model to look up.

    Returns:
        dict[str, Any]: The metadata dictionary for the model, or empty dict if not found/error.
    """
    try:
        metadata_map = _get_model_metadata_map()
        return metadata_map.get(model_name) or {}
    except Exception as e:
        logger.warning(f"Failed to get metadata for model {model_name}: {e}")
    return {}


@lru_cache(maxsize=1)
def _fetch_model_options_from_gateway() -> dict[str, list[str]]:
    """Fetches model options from the LiteLLM gateway API and categorizes them.

    Returns:
        dict[str, list[str]]: A dictionary of categorized model name lists.
    """
    model_list = fetch_raw_model_info_from_gateway()

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
    """Retrieves a categorized dictionary of available models from the LiteLLM gateway.

    Fetches models dynamically and categorizes them into 'embedding_models',
    'llm_models', and 'reranker_models'. If the fetch fails, fallback placeholders
    are returned to ensure compatibility.

    Returns:
        dict[str, list[str]]: A dictionary containing lists of categorized model names.
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
