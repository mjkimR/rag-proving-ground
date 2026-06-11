from unittest.mock import AsyncMock, MagicMock

from rag_core.adapters.vector_store.providers.qdrant import QdrantProvider


async def test_qdrant_delete_points_collection_not_exists() -> None:
    client = MagicMock()
    async_client = AsyncMock()
    async_client.collection_exists.return_value = False

    provider = QdrantProvider(client, async_client=async_client)
    await provider.delete_points("non_existent_collection", "points_selector")

    async_client.collection_exists.assert_awaited_once_with(collection_name="non_existent_collection")
    async_client.delete.assert_not_awaited()


async def test_qdrant_delete_points_collection_exists() -> None:
    client = MagicMock()
    async_client = MagicMock()  # Use MagicMock since we might want to check async methods or wait mocks
    async_client.collection_exists = AsyncMock(return_value=True)
    async_client.delete = AsyncMock()

    provider = QdrantProvider(client, async_client=async_client)
    await provider.delete_points("existent_collection", "points_selector")

    async_client.collection_exists.assert_awaited_once_with(collection_name="existent_collection")
    async_client.delete.assert_awaited_once_with(
        collection_name="existent_collection", points_selector="points_selector"
    )


async def test_qdrant_create_vector_store_hybrid(monkeypatch) -> None:
    from qdrant_client.http import models as conf

    client = MagicMock()
    mock_collection_info = MagicMock()
    mock_collection_info.config.params.vectors.size = 3
    mock_collection_info.config.params.vectors.distance = conf.Distance.COSINE
    mock_collection_info.config.params.sparse_vectors = {"sparse": MagicMock()}
    client.get_collection.return_value = mock_collection_info

    async_client = AsyncMock()
    async_client.collection_exists.return_value = False

    from langchain_core.embeddings import Embeddings

    class DummyEmbeddingModel(Embeddings):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[0.1, 0.2, 0.3]]

        def embed_query(self, text: str) -> list[float]:
            return [0.1, 0.2, 0.3]

    monkeypatch.setattr(
        "rag_core.adapters.vector_store.providers.qdrant.get_embedding_model",
        lambda name: DummyEmbeddingModel(),
    )

    provider = QdrantProvider(client, async_client=async_client)

    class DummyFastEmbedSparse:
        def __init__(self, *args, **kwargs):
            self.model_name = kwargs.get("model_name", "Qdrant/bm25")

    monkeypatch.setattr(
        "langchain_qdrant.FastEmbedSparse",
        DummyFastEmbedSparse,
    )

    await provider.create_vector_store(
        collection_name="hybrid_collection",
        model_name="dummy-dense-model",
        distance="cosine",
        retrieval_mode="hybrid",
        sparse_model="en-bm25",
    )

    async_client.create_collection.assert_awaited_once()
    kwargs = async_client.create_collection.call_args[1]
    assert kwargs["collection_name"] == "hybrid_collection"
    assert "sparse_vectors_config" in kwargs
    assert kwargs["sparse_vectors_config"] is not None
