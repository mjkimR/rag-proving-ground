from uuid import uuid4

import pytest
from langchain_core.documents import Document
from qdrant_client.http import models as qmodels
from rag_core.embeddings.schemas import EmbeddingDistanceMetric, KnowledgeEmbeddingConfig
from rag_core.retrieval import search
from rag_core.retrieval.schemas import RetrievedChunk
from rag_core.retrieval.search import retrieve_knowledge_chunks


async def test_retrieve_knowledge_chunks_queries_vector_store(monkeypatch: pytest.MonkeyPatch) -> None:
    kb_id = uuid4()
    query_str = "test query"
    embedding_config = KnowledgeEmbeddingConfig(model="test-embedding-model", distance=EmbeddingDistanceMetric.COSINE)

    # Fake vector store with similarity search implementation
    class FakeVectorStore:
        async def asimilarity_search_with_score(
            self, query: str, k: int, filter: qmodels.Filter
        ) -> list[tuple[Document, float]]:
            assert query == query_str
            assert k == 3

            # Verify filter matches our knowledge base ID
            assert filter is not None
            assert isinstance(filter.must, list)
            assert len(filter.must) == 1
            condition = filter.must[0]
            assert isinstance(condition, qmodels.FieldCondition)
            assert condition.key == "metadata.knowledge_id"
            match_value = condition.match
            assert isinstance(match_value, qmodels.MatchValue)
            assert match_value.value == str(kb_id)

            return [
                (
                    Document(
                        page_content="chunk 1 content",
                        metadata={
                            "chunk_id": "chunk_1",
                            "doc_id": "doc_123",
                            "knowledge_id": str(kb_id),
                        },
                    ),
                    0.95,
                ),
                (
                    Document(
                        page_content="chunk 2 content",
                        metadata={
                            "chunk_id": "chunk_2",
                            "doc_id": "doc_456",
                            "knowledge_id": str(kb_id),
                        },
                    ),
                    0.82,
                ),
            ]

    async def fake_get_knowledge_vector_store(config):
        return FakeVectorStore(), "collection_name", "hash_val"

    monkeypatch.setattr(search, "get_knowledge_vector_store", fake_get_knowledge_vector_store)

    results = await retrieve_knowledge_chunks(
        query=query_str,
        knowledge_base_id=kb_id,
        embedding_config=embedding_config,
        limit=3,
    )

    assert len(results) == 2
    assert isinstance(results[0], RetrievedChunk)
    assert results[0].chunk_id == "chunk_1"
    assert results[0].doc_id == "doc_123"
    assert results[0].content == "chunk 1 content"
    assert results[0].score == 0.95
    assert results[0].metadata["knowledge_id"] == str(kb_id)

    assert results[1].chunk_id == "chunk_2"
    assert results[1].doc_id == "doc_456"
    assert results[1].content == "chunk 2 content"
    assert results[1].score == 0.82
