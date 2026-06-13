"""Backend API integration helpers for graph implementations."""

from functools import lru_cache
from typing import Any
from uuid import UUID

import httpx
from app_http_client import get_http_client
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from rag_core.retrieval import RerankerConfig, RetrievedChunk


class BackendAPIException(RuntimeError):
    """Raised when the backend API returns an error status code."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Knowledge-base search failed ({status_code}): {detail}")


class GraphBackendSettings(BaseSettings):
    """Settings for backend APIs consumed by graph runtimes."""

    base_url: str = Field(default="http://127.0.0.1:8389", validation_alias="RAG_BACKEND_BASE_URL")
    timeout: float = Field(default=60.0, validation_alias="RAG_BACKEND_TIMEOUT", gt=0, le=300)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)


@lru_cache
def get_graph_backend_settings() -> GraphBackendSettings:
    return GraphBackendSettings()


async def search_multi_knowledge_bases(
    *,
    query: str,
    knowledge_base_ids: list[UUID],
    limit: int,
    reranker_config: RerankerConfig | None,
    candidate_limit: int | None,
    retrieval_mode: str | None = None,
    sparse_model: str | None = None,
    settings: GraphBackendSettings | None = None,
) -> list[RetrievedChunk]:
    backend_settings = settings or get_graph_backend_settings()
    url = f"{backend_settings.base_url.rstrip('/')}/api/v1/knowledge_bases/search"

    try:
        response = await get_http_client().post(
            url,
            json=_search_payload(
                query=query,
                knowledge_base_ids=knowledge_base_ids,
                limit=limit,
                reranker_config=reranker_config,
                candidate_limit=candidate_limit,
                retrieval_mode=retrieval_mode,
                sparse_model=sparse_model,
            ),
            timeout=backend_settings.timeout,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        detail = _response_error_detail(e.response)
        raise BackendAPIException(e.response.status_code, detail) from e
    except httpx.HTTPError as e:
        raise RuntimeError(f"Could not reach knowledge-base backend at {backend_settings.base_url!r}.") from e

    data = response.json()
    results = data.get("results", []) if isinstance(data, dict) else []
    return [RetrievedChunk.model_validate(result) for result in results]


def _search_payload(
    *,
    query: str,
    knowledge_base_ids: list[UUID],
    limit: int,
    reranker_config: RerankerConfig | None,
    candidate_limit: int | None,
    retrieval_mode: str | None = None,
    sparse_model: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "query": query,
        "knowledge_base_ids": [str(knowledge_base_id) for knowledge_base_id in knowledge_base_ids],
        "limit": limit,
    }
    if candidate_limit is not None:
        payload["candidate_limit"] = candidate_limit
    if reranker_config is not None:
        payload["reranker_config"] = reranker_config.model_dump(mode="json", exclude_none=True)
    if retrieval_mode is not None:
        payload["retrieval_mode"] = retrieval_mode
    if sparse_model is not None:
        payload["sparse_model"] = sparse_model
    return payload


def _response_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text

    detail = payload.get("detail") if isinstance(payload, dict) else payload
    return str(detail)
