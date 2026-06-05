from uuid import uuid4

import pytest
from langchain_core.documents import Document
from qdrant_client.http import models as qmodels
from rag_core.embeddings.schemas import EmbeddingDistanceMetric, KnowledgeEmbeddingConfig
from rag_core.retrieval import rerank, search
from rag_core.retrieval.schemas import RerankerConfig, RetrievedChunk
from rag_core.retrieval.search import retrieve_knowledge_chunks, retrieve_multi_knowledge_chunks


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
            assert k == 12

            # Verify filter matches our knowledge base ID
            condition = _single_field_condition(filter)
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
    assert results[0].knowledge_base_id == kb_id
    assert results[0].vector_score == 0.95
    assert results[0].rerank_score is None
    assert results[0].metadata["knowledge_id"] == str(kb_id)

    assert results[1].chunk_id == "chunk_2"
    assert results[1].doc_id == "doc_456"
    assert results[1].content == "chunk 2 content"
    assert results[1].score == 0.82


async def test_retrieve_multi_knowledge_chunks_requires_reranker_for_multiple_kbs() -> None:
    embedding_config = KnowledgeEmbeddingConfig(model="test-embedding-model", distance=EmbeddingDistanceMetric.COSINE)

    with pytest.raises(ValueError, match="reranker_config is required"):
        await retrieve_multi_knowledge_chunks(
            query="test query",
            kb_configs=[(uuid4(), embedding_config), (uuid4(), embedding_config)],
            limit=3,
        )


async def test_retrieve_multi_knowledge_chunks_reranks_multiple_kbs(monkeypatch: pytest.MonkeyPatch) -> None:
    kb_id_1 = uuid4()
    kb_id_2 = uuid4()
    embedding_config = KnowledgeEmbeddingConfig(model="test-embedding-model", distance=EmbeddingDistanceMetric.COSINE)
    seen_filters: list[qmodels.Filter] = []

    class FakeVectorStore:
        async def asimilarity_search_with_score(
            self, query: str, k: int, filter: qmodels.Filter
        ) -> list[tuple[Document, float]]:
            seen_filters.append(filter)
            assert query == "test query"
            assert k == 10
            condition = _single_field_condition(filter)
            assert isinstance(condition.match, qmodels.MatchValue)

            if condition.match.value == str(kb_id_1):
                return [
                    (
                        Document(
                            page_content="lower vector score but more relevant",
                            metadata={
                                "chunk_id": "chunk_1",
                                "doc_id": "doc_1",
                                "knowledge_id": str(kb_id_1),
                            },
                        ),
                        0.2,
                    )
                ]
            if condition.match.value == str(kb_id_2):
                return [
                    (
                        Document(
                            page_content="higher vector score but less relevant",
                            metadata={
                                "chunk_id": "chunk_2",
                                "doc_id": "doc_2",
                                "knowledge_id": str(kb_id_2),
                            },
                        ),
                        0.9,
                    )
                ]
            return []

    class FakeReranker:
        async def acompress_documents(self, documents, query: str):
            assert query == "test query"
            documents_by_chunk_id = {document.metadata["chunk_id"]: document for document in documents}
            first_source = documents_by_chunk_id["chunk_1"]
            second_source = documents_by_chunk_id["chunk_2"]
            first = first_source.model_copy(update={"metadata": {**first_source.metadata, "relevance_score": 0.99}})
            second = second_source.model_copy(update={"metadata": {**second_source.metadata, "relevance_score": 0.1}})
            return [first, second]

    async def fake_get_knowledge_vector_store(config):
        return FakeVectorStore(), "collection_name", "hash_val"

    def fake_get_reranker_model(model_name: str | None = None, **kwargs):
        assert model_name == "test-reranker"
        assert kwargs == {"top_n": 8}
        return FakeReranker()

    monkeypatch.setattr(search, "get_knowledge_vector_store", fake_get_knowledge_vector_store)
    monkeypatch.setattr(rerank, "get_reranker_model", fake_get_reranker_model)

    results = await retrieve_multi_knowledge_chunks(
        query="test query",
        kb_configs=[(kb_id_1, embedding_config), (kb_id_2, embedding_config)],
        limit=2,
        reranker_config=RerankerConfig(model="test-reranker", top_n=2),
    )

    assert len(seen_filters) == 2
    seen_filter_values = []
    for seen_filter in seen_filters:
        condition = _single_field_condition(seen_filter)
        assert isinstance(condition.match, qmodels.MatchValue)
        seen_filter_values.append(condition.match.value)
    assert sorted(seen_filter_values) == sorted([str(kb_id_1), str(kb_id_2)])
    assert [result.chunk_id for result in results] == ["chunk_1", "chunk_2"]
    assert results[0].score == 0.99
    assert results[0].vector_score == 0.2
    assert results[0].rerank_score == 0.99
    assert results[0].knowledge_base_id == kb_id_1
    assert results[1].score == 0.1
    assert results[1].vector_score == 0.9
    assert results[1].rerank_score == 0.1
    assert results[1].knowledge_base_id == kb_id_2


async def test_retrieve_multi_knowledge_chunks_uses_candidate_limit_per_kb(monkeypatch: pytest.MonkeyPatch) -> None:
    kb_id_1 = uuid4()
    kb_id_2 = uuid4()
    embedding_config = KnowledgeEmbeddingConfig(model="test-embedding-model", distance=EmbeddingDistanceMetric.COSINE)
    seen_limits: list[int] = []

    class FakeVectorStore:
        async def asimilarity_search_with_score(
            self, query: str, k: int, filter: qmodels.Filter
        ) -> list[tuple[Document, float]]:
            seen_limits.append(k)
            condition = _single_field_condition(filter)
            assert isinstance(condition.match, qmodels.MatchValue)
            return [
                (
                    Document(
                        page_content=f"content {condition.match.value}",
                        metadata={
                            "chunk_id": f"chunk_{condition.match.value}",
                            "doc_id": "doc",
                            "knowledge_id": condition.match.value,
                        },
                    ),
                    0.5,
                )
            ]

    class FakeReranker:
        async def acompress_documents(self, documents, query: str):
            return [
                document.model_copy(update={"metadata": {**document.metadata, "relevance_score": 0.9 - index}})
                for index, document in enumerate(documents)
            ]

    async def fake_get_knowledge_vector_store(config):
        return FakeVectorStore(), "collection_name", "hash_val"

    def fake_get_reranker_model(model_name: str | None = None, **kwargs):
        return FakeReranker()

    monkeypatch.setattr(search, "get_knowledge_vector_store", fake_get_knowledge_vector_store)
    monkeypatch.setattr(rerank, "get_reranker_model", fake_get_reranker_model)

    results = await retrieve_multi_knowledge_chunks(
        query="test query",
        kb_configs=[(kb_id_1, embedding_config), (kb_id_2, embedding_config)],
        limit=2,
        candidate_limit=7,
        reranker_config=RerankerConfig(model="test-reranker"),
    )

    assert results
    assert seen_limits == [7, 7]


async def test_retrieve_multi_knowledge_chunks_rejects_reranker_top_n_below_limit() -> None:
    embedding_config = KnowledgeEmbeddingConfig(model="test-embedding-model", distance=EmbeddingDistanceMetric.COSINE)

    with pytest.raises(ValueError, match=r"reranker_config\.top_n"):
        await retrieve_multi_knowledge_chunks(
            query="test query",
            kb_configs=[(uuid4(), embedding_config), (uuid4(), embedding_config)],
            limit=5,
            reranker_config=RerankerConfig(model="test-reranker", top_n=2),
        )


async def test_retrieve_multi_knowledge_chunks_can_map_reranked_documents_by_chunk_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kb_id_1 = uuid4()
    kb_id_2 = uuid4()
    embedding_config = KnowledgeEmbeddingConfig(model="test-embedding-model", distance=EmbeddingDistanceMetric.COSINE)

    class FakeVectorStore:
        async def asimilarity_search_with_score(
            self, query: str, k: int, filter: qmodels.Filter
        ) -> list[tuple[Document, float]]:
            condition = _single_field_condition(filter)
            assert isinstance(condition.match, qmodels.MatchValue)
            chunk_id = "chunk_1" if condition.match.value == str(kb_id_1) else "chunk_2"
            return [
                (
                    Document(
                        page_content="same duplicated content",
                        metadata={
                            "chunk_id": chunk_id,
                            "doc_id": "doc",
                            "knowledge_id": condition.match.value,
                        },
                    ),
                    0.5,
                )
            ]

    class FakeReranker:
        async def acompress_documents(self, documents, query: str):
            document = documents[1]
            return [
                document.model_copy(
                    update={
                        "metadata": {
                            "_retrieval_chunk_id": document.metadata["_retrieval_chunk_id"],
                            "_retrieval_knowledge_base_id": document.metadata["_retrieval_knowledge_base_id"],
                            "relevance_score": 0.9,
                        }
                    }
                )
            ]

    async def fake_get_knowledge_vector_store(config):
        return FakeVectorStore(), "collection_name", "hash_val"

    def fake_get_reranker_model(model_name: str | None = None, **kwargs):
        assert kwargs == {"top_n": 4}
        return FakeReranker()

    monkeypatch.setattr(search, "get_knowledge_vector_store", fake_get_knowledge_vector_store)
    monkeypatch.setattr(rerank, "get_reranker_model", fake_get_reranker_model)

    results = await retrieve_multi_knowledge_chunks(
        query="test query",
        kb_configs=[(kb_id_1, embedding_config), (kb_id_2, embedding_config)],
        limit=1,
        reranker_config=RerankerConfig(model="test-reranker", top_n=1),
    )

    assert len(results) == 1
    assert results[0].chunk_id == "chunk_2"
    assert results[0].knowledge_base_id == kb_id_2


def _single_field_condition(qdrant_filter: qmodels.Filter) -> qmodels.FieldCondition:
    assert isinstance(qdrant_filter.must, list)
    assert len(qdrant_filter.must) == 1
    condition = qdrant_filter.must[0]
    assert isinstance(condition, qmodels.FieldCondition)
    return condition


async def test_retrieve_chunks_deduplication_single_page(monkeypatch: pytest.MonkeyPatch) -> None:
    kb_id = uuid4()
    query_str = "test query"
    embedding_config = KnowledgeEmbeddingConfig(model="test-embedding-model", distance=EmbeddingDistanceMetric.COSINE)

    class FakeVectorStore:
        async def asimilarity_search_with_score(
            self, query: str, k: int, filter: qmodels.Filter
        ) -> list[tuple[Document, float]]:
            assert k == 8  # limit(2) * 4 oversampling
            return [
                (
                    Document(
                        page_content="chunk 1 content",
                        metadata={"chunk_id": "chunk_1", "doc_id": "doc_1", "page_ids": ["page_1"]},
                    ),
                    0.9,
                ),
                (
                    Document(
                        page_content="chunk 2 content",
                        metadata={"chunk_id": "chunk_2", "doc_id": "doc_1", "page_ids": ["page_1"]},  # same page
                    ),
                    0.8,
                ),
                (
                    Document(
                        page_content="chunk 3 content",
                        metadata={"chunk_id": "chunk_3", "doc_id": "doc_1", "page_ids": ["page_2"]},  # new page
                    ),
                    0.7,
                ),
            ]

    async def fake_get_knowledge_vector_store(config):
        return FakeVectorStore(), "collection_name", "hash_val"

    monkeypatch.setattr(search, "get_knowledge_vector_store", fake_get_knowledge_vector_store)

    results = await retrieve_knowledge_chunks(
        query=query_str,
        knowledge_base_id=kb_id,
        embedding_config=embedding_config,
        limit=2,
    )

    assert len(results) == 2
    assert results[0].chunk_id == "chunk_1"
    assert results[1].chunk_id == "chunk_3"  # chunk 2 is skipped due to page_1 deduplication


async def test_retrieve_chunks_deduplication_multi_page(monkeypatch: pytest.MonkeyPatch) -> None:
    kb_id = uuid4()
    query_str = "test query"
    embedding_config = KnowledgeEmbeddingConfig(model="test-embedding-model", distance=EmbeddingDistanceMetric.COSINE)

    class FakeVectorStore:
        async def asimilarity_search_with_score(
            self, query: str, k: int, filter: qmodels.Filter
        ) -> list[tuple[Document, float]]:
            return [
                (
                    Document(
                        page_content="chunk 1 content",
                        metadata={"chunk_id": "chunk_1", "doc_id": "doc_1", "page_ids": ["page_1", "page_2"]},
                    ),
                    0.9,
                ),
                (
                    Document(
                        page_content="chunk 2 content",
                        metadata={
                            "chunk_id": "chunk_2",
                            "doc_id": "doc_1",
                            "page_ids": ["page_2"],
                        },  # page_2 already seen in chunk 1
                    ),
                    0.8,
                ),
                (
                    Document(
                        page_content="chunk 3 content",
                        metadata={
                            "chunk_id": "chunk_3",
                            "doc_id": "doc_1",
                            "page_ids": ["page_2", "page_3"],
                        },  # page_3 is new, so kept
                    ),
                    0.7,
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
    assert results[0].chunk_id == "chunk_1"
    assert results[1].chunk_id == "chunk_3"  # chunk 2 is skipped because all its page_ids (page_2) were seen
