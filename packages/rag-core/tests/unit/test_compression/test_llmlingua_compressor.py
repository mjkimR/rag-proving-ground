import uuid

import httpx
import pytest
import respx
from rag_core.compression.llmlingua_compressor import LLMLinguaCompressor
from rag_core.config import get_llmlingua_settings
from rag_core.retrieval.schemas import RetrievedChunk


@pytest.fixture
def compressor():
    return LLMLinguaCompressor(max_chunks_to_process=2)

@pytest.fixture
def mock_chunks():
    kb_id = uuid.uuid4()
    return [
        RetrievedChunk(
            chunk_id="chunk1",
            doc_id="doc1",
            content="This is the first chunk.",
            score=0.9,
            knowledge_base_id=kb_id,
            vector_score=0.9,
            rerank_score=0.9,
        ),
        RetrievedChunk(
            chunk_id="chunk2",
            doc_id="doc2",
            content="This is the second chunk which is longer.",
            score=0.4,
            knowledge_base_id=kb_id,
            vector_score=0.4,
            rerank_score=0.4,
        ),
    ]


@pytest.mark.asyncio
async def test_llmlingua_compressor_empty_chunks(compressor):
    result = await compressor.compress("query", [])
    assert result == []


@pytest.mark.asyncio
@respx.mock
async def test_llmlingua_compressor_success(compressor, mock_chunks):
    settings = get_llmlingua_settings()
    url = f"{settings.base_url.rstrip('/')}/compress"

    # Mock the external API
    respx.post(url).mock(
        return_value=httpx.Response(
            200,
            json={"compressed_context": "Compressed chunk text"}
        )
    )

    result = await compressor.compress("test query", mock_chunks)

    # Check that it processed both chunks (as a single batch or multiple)
    assert len(result) > 0
    # Since it compressed both in a single string based on mock, it likely returns 1 chunk
    assert "Compressed chunk text" in result[0].content


@pytest.mark.asyncio
@respx.mock
async def test_llmlingua_compressor_api_error(compressor, mock_chunks):
    settings = get_llmlingua_settings()
    url = f"{settings.base_url.rstrip('/')}/compress"

    # Mock the external API to fail
    respx.post(url).mock(return_value=httpx.Response(500))

    result = await compressor.compress("test query", mock_chunks)

    # On failure, it should fallback to returning the original batch
    assert len(result) == len(mock_chunks)
    assert result[0].content == mock_chunks[0].content
    assert result[1].content == mock_chunks[1].content
