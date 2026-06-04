import asyncio
from dataclasses import dataclass
from uuid import UUID

from langchain_core.documents import Document
from loguru import logger
from qdrant_client.http import models as qmodels

from rag_core.ai.models import get_reranker_model
from rag_core.embeddings.indexing import get_knowledge_vector_store
from rag_core.embeddings.schemas import (
    KnowledgeEmbeddingConfig,
    resolve_knowledge_embedding_config,
)
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
    """Retrieve similar document chunks for a query from a specific knowledge base."""

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
    """Retrieve chunks from one or more knowledge bases and optionally rerank the merged candidates."""

    if limit < 1:
        raise ValueError("limit must be greater than or equal to 1.")
    if candidate_limit is not None and candidate_limit < 1:
        raise ValueError("candidate_limit must be greater than or equal to 1.")

    unique_kb_ids = {knowledge_base_id for knowledge_base_id, _ in kb_configs}
    if len(unique_kb_ids) >= 2 and reranker_config is None:
        raise ValueError("reranker_config is required when searching multiple knowledge bases.")
    _validate_reranker_config(reranker_config=reranker_config, limit=limit)

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
        return await _rerank_chunks(
            query=query,
            chunks=candidates,
            limit=limit,
            reranker_config=reranker_config,
        )

    return sorted(candidates, key=lambda chunk: chunk.score, reverse=True)[:limit]


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


def _validate_reranker_config(*, reranker_config: RerankerConfig | None, limit: int) -> None:
    if reranker_config is not None and reranker_config.top_n is not None and reranker_config.top_n < limit:
        raise ValueError("reranker_config.top_n must be greater than or equal to limit.")


def _default_candidate_limit(
    *,
    limit: int,
    kb_count: int,
    reranker_config: RerankerConfig | None,
) -> int:
    if reranker_config is None or kb_count < 2:
        return limit
    return max(limit * 2, 10)


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


async def _rerank_chunks(
    *,
    query: str,
    chunks: list[RetrievedChunk],
    limit: int,
    reranker_config: RerankerConfig,
) -> list[RetrievedChunk]:
    if not chunks:
        return []

    compressor = get_reranker_model(
        model_name=reranker_config.model,
        top_n=_reranker_top_n(reranker_config=reranker_config, limit=limit),
    )
    chunks_by_identity = {
        _chunk_identity(chunk_id=chunk.chunk_id, knowledge_base_id=chunk.knowledge_base_id): chunk for chunk in chunks
    }
    documents = [
        Document(
            page_content=chunk.content,
            metadata={
                **chunk.metadata,
                "_retrieval_index": index,
                "_retrieval_chunk_id": chunk.chunk_id,
                "_retrieval_knowledge_base_id": str(chunk.knowledge_base_id),
            },
        )
        for index, chunk in enumerate(chunks)
    ]
    reranked_documents = await compressor.acompress_documents(documents, query=query)

    reranked_chunks: list[RetrievedChunk] = []
    for document in reranked_documents:
        rerank_score = document.metadata.get("relevance_score")
        if rerank_score is None:
            continue

        chunk = _chunk_from_reranked_document(document=document, chunks=chunks, chunks_by_identity=chunks_by_identity)
        if chunk is None:
            continue

        final_score = float(rerank_score)
        reranked_chunks.append(
            chunk.model_copy(
                update={
                    "score": final_score,
                    "rerank_score": final_score,
                }
            )
        )

    return sorted(reranked_chunks, key=lambda chunk: chunk.score, reverse=True)[:limit]


def _reranker_top_n(*, reranker_config: RerankerConfig, limit: int) -> int:
    if reranker_config.top_n is None:
        return limit
    return reranker_config.top_n


def _chunk_from_reranked_document(
    *,
    document: Document,
    chunks: list[RetrievedChunk],
    chunks_by_identity: dict[tuple[str, str], RetrievedChunk],
) -> RetrievedChunk | None:
    index = document.metadata.get("_retrieval_index")
    if isinstance(index, int) and 0 <= index < len(chunks):
        return chunks[index]

    chunk_id = document.metadata.get("_retrieval_chunk_id") or document.metadata.get("chunk_id")
    knowledge_base_id = document.metadata.get("_retrieval_knowledge_base_id") or document.metadata.get("knowledge_id")
    if chunk_id is None or knowledge_base_id is None:
        return None
    return chunks_by_identity.get(_chunk_identity(chunk_id=str(chunk_id), knowledge_base_id=knowledge_base_id))


def _chunk_identity(*, chunk_id: str, knowledge_base_id: UUID | str) -> tuple[str, str]:
    return chunk_id, str(knowledge_base_id)
