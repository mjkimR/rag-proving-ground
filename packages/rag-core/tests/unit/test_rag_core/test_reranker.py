import litellm
import pytest
from langchain_core.documents import Document
from pydantic import SecretStr
from rag_core.ai.reranker import LiteLLMRerankCompressor


def test_truncate_text_to_tokens() -> None:
    compressor = LiteLLMRerankCompressor(
        model="test-reranker",
        api_base="http://localhost:1234",
        api_key=SecretStr("test-key"),
        max_tokens_per_doc=10,
    )

    # A short text should stay intact
    assert compressor._truncate_doc_text("hello world") == "hello world"

    # Empty string should stay empty
    assert compressor._truncate_doc_text("") == ""

    # A long text exceeding max_tokens (e.g. 2 tokens) should be truncated.
    compressor_short = LiteLLMRerankCompressor(
        model="test-reranker",
        api_base="http://localhost:1234",
        api_key=SecretStr("test-key"),
        max_tokens_per_doc=2,
    )
    truncated = compressor_short._truncate_doc_text("one two three four five")
    # The output should be shorter
    assert len(truncated.split()) <= 2


def test_compress_documents_truncates_input_but_returns_original_content(monkeypatch: pytest.MonkeyPatch) -> None:
    # Prepare documents, one of which is long
    long_content = "word " * 100  # 100 tokens/words
    documents = [
        Document(page_content="short document", metadata={"id": 1}),
        Document(page_content=long_content, metadata={"id": 2}),
    ]

    compressor = LiteLLMRerankCompressor(
        model="test-reranker",
        api_base="http://localhost:1234",
        api_key=SecretStr("test-key"),
        max_tokens_per_doc=10,
        top_n=2,
    )

    seen_documents = []

    def mock_rerank(model, query, documents, **kwargs):
        nonlocal seen_documents
        seen_documents = documents
        return {
            "results": [
                {"index": 0, "relevance_score": 0.9},
                {"index": 1, "relevance_score": 0.8},
            ]
        }

    monkeypatch.setattr(litellm, "rerank", mock_rerank)

    results = compressor.compress_documents(documents, query="test query")

    # Assertions
    assert len(results) == 2

    # Verify that the documents sent to the mock rerank were truncated
    assert seen_documents[0] == "short document"
    assert len(seen_documents[1].split()) <= 10  # Truncated to <= 10 tokens (approx 10 words)

    # Verify that the returned documents have the ORIGINAL, UNTRUNCATED page content
    assert results[0].page_content == "short document"
    assert results[0].metadata["relevance_score"] == 0.9
    assert results[1].page_content == long_content
    assert results[1].metadata["relevance_score"] == 0.8


async def test_acompress_documents_truncates_input_but_returns_original_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Prepare documents, one of which is long
    long_content = "word " * 100  # 100 tokens/words
    documents = [
        Document(page_content="short document", metadata={"id": 1}),
        Document(page_content=long_content, metadata={"id": 2}),
    ]

    compressor = LiteLLMRerankCompressor(
        model="test-reranker",
        api_base="http://localhost:1234",
        api_key=SecretStr("test-key"),
        max_tokens_per_doc=10,
        top_n=2,
    )

    seen_documents = []

    async def mock_arerank(model, query, documents, **kwargs):
        nonlocal seen_documents
        seen_documents = documents
        return {
            "results": [
                {"index": 0, "relevance_score": 0.95},
                {"index": 1, "relevance_score": 0.85},
            ]
        }

    monkeypatch.setattr(litellm, "arerank", mock_arerank)

    results = await compressor.acompress_documents(documents, query="test query")

    # Assertions
    assert len(results) == 2

    # Verify that the documents sent to the mock arerank were truncated
    assert seen_documents[0] == "short document"
    assert len(seen_documents[1].split()) <= 10

    # Verify that the returned documents have the ORIGINAL, UNTRUNCATED page content
    assert results[0].page_content == "short document"
    assert results[0].metadata["relevance_score"] == 0.95
    assert results[1].page_content == long_content
    assert results[1].metadata["relevance_score"] == 0.85
