import pytest
from rag_core.embeddings import (
    EmbeddingDistanceMetric,
    KnowledgeEmbeddingConfig,
    delete_document_vectors,
    indexing,
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
    }
    assert knowledge_embedding_config_hash(config) == knowledge_embedding_config_hash(config)
    assert knowledge_vector_collection_name(knowledge_embedding_config_hash(config)).startswith("vector_store_")


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
