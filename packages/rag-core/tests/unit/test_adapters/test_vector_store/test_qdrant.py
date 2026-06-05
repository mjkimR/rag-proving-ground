import pytest
from unittest.mock import AsyncMock, MagicMock
from rag_core.adapters.vector_store.providers.qdrant import QdrantProvider


@pytest.mark.asyncio
async def test_qdrant_delete_points_collection_not_exists() -> None:
    client = MagicMock()
    async_client = AsyncMock()
    async_client.collection_exists.return_value = False

    provider = QdrantProvider(client, async_client=async_client)
    await provider.delete_points("non_existent_collection", "points_selector")

    async_client.collection_exists.assert_awaited_once_with(collection_name="non_existent_collection")
    async_client.delete.assert_not_awaited()


@pytest.mark.asyncio
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
