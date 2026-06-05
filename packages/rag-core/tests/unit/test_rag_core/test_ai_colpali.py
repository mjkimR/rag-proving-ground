from unittest.mock import MagicMock

import pytest
from PIL import Image
from rag_core.ai.colpali import ColPaliModel


@pytest.mark.asyncio
async def test_colpali_model_encode_queries(mocker):
    # Mock httpx.AsyncClient response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"embedding": [[0.1, 0.2], [0.3, 0.4]]}]}
    mock_response.raise_for_status = MagicMock()

    mock_post = mocker.patch("httpx.AsyncClient.post", return_value=mock_response)

    model = ColPaliModel()
    embeddings = await model.encode_queries(["hello"])

    assert len(embeddings) == 1
    assert embeddings[0] == [[0.1, 0.2], [0.3, 0.4]]
    mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_colpali_model_encode_images(mocker):
    # Mock httpx.AsyncClient response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"embedding": [[0.5, 0.6], [0.7, 0.8]]}]}
    mock_response.raise_for_status = MagicMock()

    mock_post = mocker.patch("httpx.AsyncClient.post", return_value=mock_response)

    # Mock Pillow Image save
    img = Image.new("RGB", (100, 100))

    model = ColPaliModel()
    embeddings = await model.encode_images([img])

    assert len(embeddings) == 1
    assert embeddings[0] == [[0.5, 0.6], [0.7, 0.8]]
    mock_post.assert_called_once()
