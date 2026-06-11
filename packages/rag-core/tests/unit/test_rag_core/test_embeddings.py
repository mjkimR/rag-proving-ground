import pytest
from rag_core.embeddings import (
    EmbeddingDistanceMetric,
    KnowledgeEmbeddingConfig,
    RetrievalMode,
    SparseEmbeddingModel,
    delete_document_vectors,
    indexing,
    is_colpali_model,
    knowledge_embedding_config_hash,
    knowledge_embedding_config_payload,
    knowledge_vector_collection_name,
    resolve_knowledge_embedding_config,
)


def test_resolve_knowledge_embedding_config_uses_default_model() -> None:
    config = resolve_knowledge_embedding_config(None, default_model="embedding-default")

    assert config == KnowledgeEmbeddingConfig(model="embedding-default", distance=EmbeddingDistanceMetric.COSINE)


def test_knowledge_embedding_config_hash_is_stable() -> None:
    config = resolve_knowledge_embedding_config(
        {"distance": "cosine", "model": "embedding-a"},
        default_model="ignored",
    )

    assert knowledge_embedding_config_payload(config) == {
        "model": "embedding-a",
        "distance": "cosine",
        "use_colpali": False,
        "colpali_model": None,
        "retrieval_mode": "dense",
        "sparse_model": None,
    }
    assert knowledge_embedding_config_hash(config) == knowledge_embedding_config_hash(config)
    assert knowledge_vector_collection_name(knowledge_embedding_config_hash(config)).startswith("vector_store_")


def test_resolve_knowledge_embedding_config_with_colpali() -> None:
    config = resolve_knowledge_embedding_config(
        {"distance": "cosine", "use_colpali": True, "colpali_model": "vidore/colpali-v1.3-merged"},
        default_model="ignored",
    )

    assert config.model == "ignored"
    assert config.use_colpali is True
    assert config.colpali_model == "vidore/colpali-v1.3-merged"
    assert is_colpali_model(config.colpali_model) is True


def test_knowledge_embedding_config_hash_changes_with_distance() -> None:
    cosine_config = KnowledgeEmbeddingConfig(model="embedding-a", distance=EmbeddingDistanceMetric.COSINE)
    dot_config = KnowledgeEmbeddingConfig(model="embedding-a", distance=EmbeddingDistanceMetric.DOT)

    assert knowledge_embedding_config_hash(cosine_config) != knowledge_embedding_config_hash(dot_config)


def test_knowledge_embedding_config_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError):
        KnowledgeEmbeddingConfig.model_validate({"model": "embedding-a", "unknown": True})


async def test_delete_document_vectors_delegates_to_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    class FakeProvider:
        async def delete_points(self, collection_name: str, points_selector) -> None:
            calls.append((collection_name, points_selector))

    monkeypatch.setattr(indexing, "get_vector_store_provider", lambda: FakeProvider())

    await delete_document_vectors("collection-a", "doc-123")

    assert calls[0][0] == "collection-a"
    assert calls[0][1].filter.must[0].key == "metadata.doc_id"
    assert calls[0][1].filter.must[0].match.value == "doc-123"


def test_resolve_knowledge_embedding_config_with_hybrid_sparse() -> None:
    config_hybrid = resolve_knowledge_embedding_config(
        {"retrieval_mode": "hybrid", "model": "embedding-a", "sparse_model": "some-sparse-model"},
    )
    assert config_hybrid.retrieval_mode == "hybrid"
    assert config_hybrid.sparse_model == "some-sparse-model"

    config_sparse_default = resolve_knowledge_embedding_config(
        {"retrieval_mode": "sparse", "model": "embedding-a"},
    )
    assert config_sparse_default.retrieval_mode == "sparse"
    assert config_sparse_default.sparse_model == SparseEmbeddingModel.EN_BM25.value

    with pytest.raises(NotImplementedError, match="Hybrid or sparse search with ColPali is not implemented yet"):
        KnowledgeEmbeddingConfig(use_colpali=True, retrieval_mode=RetrievalMode.HYBRID)
