from uuid import UUID

from langchain_core.documents import Document

from rag_core.ai.models import get_reranker_model
from rag_core.retrieval.schemas import RerankerConfig, RetrievedChunk


def validate_reranker_config(*, reranker_config: RerankerConfig | None, limit: int) -> None:
    """Validate that the reranker configuration's top_n is compatible with the limit."""
    if reranker_config is not None and reranker_config.top_n is not None and reranker_config.top_n < limit:
        raise ValueError("reranker_config.top_n must be greater than or equal to limit.")


async def rerank_chunks(
    *,
    query: str,
    chunks: list[RetrievedChunk],
    limit: int,
    reranker_config: RerankerConfig,
) -> list[RetrievedChunk]:
    """Rerank search result chunks using the specified reranker model."""
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
