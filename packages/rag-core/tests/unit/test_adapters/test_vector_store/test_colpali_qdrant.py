from unittest.mock import MagicMock

from langchain_core.documents import Document
from PIL import Image
from rag_core.adapters.vector_store.providers.colpali_qdrant import ColPaliQdrantStore


async def test_colpali_qdrant_store_aadd_documents(mocker):
    # Mock clients
    mock_qdrant = MagicMock()
    mock_async_qdrant = MagicMock()
    mock_async_qdrant.upsert = mocker.AsyncMock()

    # Mock storage client
    mock_storage = MagicMock()
    mock_storage.download_file = mocker.AsyncMock(return_value=b"jpeg_data")
    mocker.patch(
        "rag_core.adapters.vector_store.providers.colpali_qdrant.get_storage_client", return_value=mock_storage
    )

    # Mock PIL Image.open
    mock_img = Image.new("RGB", (100, 100))
    mocker.patch("PIL.Image.open", return_value=mock_img)

    # Mock ColPaliModel
    mock_model = MagicMock()
    mock_model.encode_images = mocker.AsyncMock(return_value=[[[0.1, 0.2]]])

    store = ColPaliQdrantStore(
        client=mock_qdrant,
        async_client=mock_async_qdrant,
        collection_name="colpali_collection",
        colpali_model=mock_model,
    )

    docs = [Document(page_content="page 1", metadata={"image_storage_path": "path/to/page1.jpg"})]

    point_ids = await store.aadd_documents(docs)

    assert len(point_ids) == 1
    mock_storage.download_file.assert_called_once_with("path/to/page1.jpg")
    mock_model.encode_images.assert_called_once_with([mock_img])
    mock_async_qdrant.upsert.assert_called_once()


async def test_colpali_qdrant_store_asimilarity_search_with_score(mocker):
    # Mock clients
    mock_qdrant = MagicMock()
    mock_async_qdrant = MagicMock()

    # Mock query_points response
    mock_point = MagicMock()
    mock_point.score = 0.95
    mock_point.payload = {"page_content": "searched page", "metadata": {"doc_id": "doc_1"}}

    mock_results = MagicMock()
    mock_results.points = [mock_point]

    mock_async_qdrant.query_points = mocker.AsyncMock(return_value=mock_results)

    # Mock ColPaliModel
    mock_model = MagicMock()
    mock_model.encode_queries = mocker.AsyncMock(return_value=[[[0.1, 0.2]]])

    store = ColPaliQdrantStore(
        client=mock_qdrant,
        async_client=mock_async_qdrant,
        collection_name="colpali_collection",
        colpali_model=mock_model,
    )

    results = await store.asimilarity_search_with_score("hello", k=1)

    assert len(results) == 1
    doc, score = results[0]
    assert doc.page_content == "searched page"
    assert doc.metadata["doc_id"] == "doc_1"
    assert score == 0.95
    mock_model.encode_queries.assert_called_once_with(["hello"])
    mock_async_qdrant.query_points.assert_called_once()
