import uuid
from unittest.mock import patch

import pytest
from rag_core.compression.prefilter import RerankerPrefilter
from rag_core.retrieval.schemas import RerankerConfig, RetrievedChunk


@pytest.fixture
def prefilter():
    config = RerankerConfig(model="test-model", top_n=10)
    return RerankerPrefilter(limit=5, reranker_config=config)

@pytest.mark.asyncio
async def test_reranker_prefilter_empty(prefilter):
    result = await prefilter.compress("query", [])
    assert result == []

@pytest.mark.asyncio
async def test_reranker_prefilter_delegates(prefilter):
    chunks = [
        RetrievedChunk(
            chunk_id="c1",
            doc_id="d1",
            content="test",
            score=0.5,
            knowledge_base_id=uuid.uuid4(),
            vector_score=0.5
        )
    ]

    with patch("rag_core.compression.prefilter.rerank_chunks") as mock_rerank:
        mock_rerank.return_value = chunks

        result = await prefilter.compress("query", chunks)

        mock_rerank.assert_called_once_with(
            query="query",
            chunks=chunks,
            limit=prefilter.limit,
            reranker_config=prefilter.reranker_config
        )
        assert result == chunks
