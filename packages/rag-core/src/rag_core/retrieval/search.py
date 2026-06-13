import asyncio
from dataclasses import dataclass
from uuid import UUID

from loguru import logger
from qdrant_client.http import models as qmodels

from rag_core.embeddings.indexing import get_knowledge_vector_store
from rag_core.embeddings.schemas import (
    KnowledgeEmbeddingConfig,
    resolve_knowledge_embedding_config,
)
from rag_core.retrieval.rerank import rerank_chunks, validate_reranker_config
from rag_core.retrieval.schemas import RerankerConfig, RetrievedChunk


@dataclass(frozen=True)
class _ResolvedKnowledgeConfig:
    knowledge_base_id: UUID
    embedding_config: KnowledgeEmbeddingConfig


async def retrieve_knowledge_chunks(
    query: str,
    knowledge_base_id: UUID,
    embedding_config: KnowledgeEmbeddingConfig,
    *,
    limit: int = 5,
) -> list[RetrievedChunk]:
    """Retrieves similar document chunks for a query from a specific knowledge base.

    Args:
        query: The search query text.
        knowledge_base_id: The ID of the target knowledge base.
        embedding_config: The embedding configuration associated with the knowledge base.
        limit: The maximum number of retrieved chunks to return. Defaults to 5.

    Returns:
        list[RetrievedChunk]: A list of retrieved chunk instances sorted by relevance.
    """

    return await retrieve_multi_knowledge_chunks(
        query=query,
        kb_configs=[(knowledge_base_id, embedding_config)],
        limit=limit,
    )


async def retrieve_multi_knowledge_chunks(
    query: str,
    kb_configs: list[tuple[UUID, KnowledgeEmbeddingConfig]],
    *,
    limit: int = 5,
    reranker_config: RerankerConfig | None = None,
    candidate_limit: int | None = None,
) -> list[RetrievedChunk]:
    """Retrieves chunks from one or more knowledge bases and optionally reranks the merged candidates.

    If more than one knowledge base is queried, `reranker_config` must be provided to normalize
    and compare the similarity scores of candidates across different knowledge bases.

    Args:
        query: The search query text.
        kb_configs: A list of tuples containing the knowledge base ID and its embedding config.
        limit: The final maximum number of retrieved chunks to return. Defaults to 5.
        reranker_config: Optional configuration for the reranking step.
        candidate_limit: Optional limit on the number of candidates to retrieve per knowledge base before reranking.

    Returns:
        list[RetrievedChunk]: A list of deduplicated retrieved chunk instances.

    Raises:
        ValueError: If `limit` or `candidate_limit` is less than 1, or if multiple knowledge bases
            are queried but no `reranker_config` is specified.
    """

    if limit < 1:
        raise ValueError("limit must be greater than or equal to 1.")
    if candidate_limit is not None and candidate_limit < 1:
        raise ValueError("candidate_limit must be greater than or equal to 1.")

    unique_kb_ids = {knowledge_base_id for knowledge_base_id, _ in kb_configs}
    if len(unique_kb_ids) >= 2 and reranker_config is None:
        raise ValueError("reranker_config is required when searching multiple knowledge bases.")
    validate_reranker_config(reranker_config=reranker_config, limit=limit)

    resolved_configs = _resolve_configs(kb_configs)
    if not resolved_configs:
        return []

    per_kb_candidate_limit = candidate_limit or _default_candidate_limit(
        limit=limit,
        kb_count=len(resolved_configs),
        reranker_config=reranker_config,
    )
    search_tasks = [
        _search_knowledge_base(
            query=query,
            config=config,
            limit=per_kb_candidate_limit,
        )
        for config in resolved_configs
    ]
    search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
    candidates = []
    for result, config in zip(search_results, resolved_configs, strict=True):
        if isinstance(result, BaseException):
            logger.opt(exception=result).error(
                f"Error retrieving chunks for knowledge base {config.knowledge_base_id}: {result}"
            )
        elif isinstance(result, list):
            candidates.extend(result)

    if reranker_config is not None:
        # Create an oversampled reranker config to allow reranking more candidates
        oversampled_reranker_config = reranker_config.model_copy()
        if oversampled_reranker_config.top_n is not None:
            oversampled_reranker_config.top_n = max(oversampled_reranker_config.top_n, limit * 4)
        else:
            oversampled_reranker_config.top_n = limit * 4

        ranked_chunks = await rerank_chunks(
            query=query,
            chunks=candidates,
            limit=limit * 4,
            reranker_config=oversampled_reranker_config,
        )
    else:
        ranked_chunks = sorted(candidates, key=lambda chunk: chunk.score, reverse=True)

    # Perform memory-based deduplication
    seen_pages = set()
    deduped_chunks = []
    for chunk in ranked_chunks:
        page_ids = chunk.metadata.get("page_ids")
        if isinstance(page_ids, list) and page_ids:
            if all(p in seen_pages for p in page_ids):
                continue
            seen_pages.update(page_ids)

        deduped_chunks.append(chunk)
        if len(deduped_chunks) >= limit:
            break

    return deduped_chunks


def _resolve_configs(kb_configs: list[tuple[UUID, KnowledgeEmbeddingConfig]]) -> list[_ResolvedKnowledgeConfig]:
    seen_kb_ids: set[UUID] = set()
    resolved_configs: list[_ResolvedKnowledgeConfig] = []
    for knowledge_base_id, embedding_config in kb_configs:
        if knowledge_base_id in seen_kb_ids:
            continue
        seen_kb_ids.add(knowledge_base_id)

        resolved_config = resolve_knowledge_embedding_config(embedding_config)
        resolved_configs.append(
            _ResolvedKnowledgeConfig(
                knowledge_base_id=knowledge_base_id,
                embedding_config=resolved_config,
            )
        )
    return resolved_configs


def _default_candidate_limit(
    *,
    limit: int,
    kb_count: int,
    reranker_config: RerankerConfig | None,
) -> int:
    if reranker_config is None or kb_count < 2:
        return limit * 4
    return max(limit * 4, 10)


async def _search_knowledge_base(
    *,
    query: str,
    config: _ResolvedKnowledgeConfig,
    limit: int,
) -> list[RetrievedChunk]:
    vector_store, _, _ = await get_knowledge_vector_store(config.embedding_config)

    results = await vector_store.asimilarity_search_with_score(
        query=query,
        k=limit,
        filter=_knowledge_base_filter(config.knowledge_base_id),
    )

    retrieved_chunks: list[RetrievedChunk] = []
    for doc, score in results:
        metadata = doc.metadata
        chunk_id = metadata.get("chunk_id", "")
        doc_id = metadata.get("doc_id", "")
        vector_score = float(score)

        retrieved_chunks.append(
            RetrievedChunk(
                chunk_id=str(chunk_id),
                doc_id=str(doc_id),
                content=doc.page_content,
                score=vector_score,
                knowledge_base_id=_metadata_knowledge_base_id(metadata, fallback=config.knowledge_base_id),
                vector_score=vector_score,
                metadata=metadata,
            )
        )

    return retrieved_chunks


def _knowledge_base_filter(knowledge_base_id: UUID) -> qmodels.Filter:
    return qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="metadata.knowledge_id",
                match=qmodels.MatchValue(value=str(knowledge_base_id)),
            )
        ]
    )


def _metadata_knowledge_base_id(metadata: dict, *, fallback: UUID) -> UUID:
    knowledge_base_id = metadata.get("knowledge_id") or metadata.get("knowledge_base_id")
    if knowledge_base_id is None:
        return fallback
    try:
        return UUID(str(knowledge_base_id))
    except ValueError:
        return fallback
