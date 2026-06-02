from uuid import UUID

from qdrant_client.http import models as qmodels

from rag_core.embeddings.indexing import get_knowledge_vector_store
from rag_core.embeddings.schemas import KnowledgeEmbeddingConfig
from rag_core.retrieval.schemas import RetrievedChunk


async def retrieve_knowledge_chunks(
    query: str,
    knowledge_base_id: UUID,
    embedding_config: KnowledgeEmbeddingConfig,
    *,
    limit: int = 5,
) -> list[RetrievedChunk]:
    """Retrieve similar document chunks for a query from a specific knowledge base."""

    vector_store, _, _ = await get_knowledge_vector_store(embedding_config)

    qdrant_filter = qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="metadata.knowledge_id",
                match=qmodels.MatchValue(value=str(knowledge_base_id)),
            )
        ]
    )

    # asimilarity_search_with_score is async-safe and maps to the underlying Qdrant client call
    results = await vector_store.asimilarity_search_with_score(
        query=query,
        k=limit,
        filter=qdrant_filter,
    )

    retrieved_chunks = []
    for doc, score in results:
        metadata = doc.metadata
        chunk_id = metadata.get("chunk_id", "")
        doc_id = metadata.get("doc_id", "")

        retrieved_chunks.append(
            RetrievedChunk(
                chunk_id=str(chunk_id),
                doc_id=str(doc_id),
                content=doc.page_content,
                score=float(score),
                metadata=metadata,
            )
        )

    return retrieved_chunks
