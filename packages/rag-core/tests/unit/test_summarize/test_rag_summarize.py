from typing import Any, cast
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from rag_core.retrieval.schemas import RetrievedChunk
from rag_core.summarize.rag_summarize import TargetedSummarizer


class MockLLM:
    """A minimal mock class that mimics a LangChain BaseChatModel or Runnable with ainvoke."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[list[Any]] = []

    async def ainvoke(self, messages: list[Any]) -> Any:
        self.calls.append(messages)

        class MockResponse:
            content = self.response

        return MockResponse()


@pytest.mark.asyncio
async def test_targeted_summarizer_empty_chunks() -> None:
    llm = MockLLM("No context response")
    summarizer = TargetedSummarizer(llm=cast(Any, llm), model_name="gpt-4o-mini")

    res = await summarizer.summarize("What is anti-gravity?", [])
    assert res == "No context response"
    assert len(llm.calls) == 1

    messages = llm.calls[0]
    assert isinstance(messages[0], SystemMessage)
    assert "No knowledge-base context was retrieved for this turn." in messages[0].content
    assert isinstance(messages[1], HumanMessage)
    assert messages[1].content == "What is anti-gravity?"


@pytest.mark.asyncio
async def test_targeted_summarizer_with_chunks() -> None:
    llm = MockLLM("Standard answer")
    summarizer = TargetedSummarizer(llm=cast(Any, llm), model_name="gpt-4o-mini")

    kb_id = uuid4()
    doc_id = str(uuid4())
    chunk_id = str(uuid4())

    chunks = [
        RetrievedChunk(
            knowledge_base_id=kb_id,
            doc_id=doc_id,
            chunk_id=chunk_id,
            score=0.8765,
            vector_score=0.8765,
            content="This is the fallback text content.",
            page_content="Anti-gravity is a hypothetical force or technology that cancels gravity.",
            metadata={"source": "physics_101.pdf", "page": 42},
        )
    ]

    res = await summarizer.summarize("Explain anti-gravity.", chunks)
    assert res == "Standard answer"
    assert len(llm.calls) == 1

    messages = llm.calls[0]
    assert isinstance(messages[0], SystemMessage)
    sys_content = messages[0].content
    assert "You are a retrieval-augmented assistant." in sys_content
    assert "physics_101.pdf" in sys_content
    assert "page=42" in sys_content
    assert "score=0.8765" in sys_content
    assert "Anti-gravity is a hypothetical force" in sys_content

    assert isinstance(messages[1], HumanMessage)
    assert messages[1].content == "Explain anti-gravity."


@pytest.mark.asyncio
async def test_targeted_summarizer_metadata_extraction() -> None:
    llm = MockLLM("Answer")
    summarizer = TargetedSummarizer(llm=cast(Any, llm), model_name="gpt-4o-mini")

    # Test page_number and filename extraction
    chunks = [
        RetrievedChunk(
            knowledge_base_id=uuid4(),
            doc_id=str(uuid4()),
            chunk_id=str(uuid4()),
            score=0.9,
            vector_score=0.9,
            content="Chunk 1 content",
            metadata={"filename": "doc1.txt", "page_number": 10},
        ),
        RetrievedChunk(
            knowledge_base_id=uuid4(),
            doc_id=str(uuid4()),
            chunk_id=str(uuid4()),
            score=0.8,
            vector_score=0.8,
            content="Chunk 2 content",
            metadata={"title": "Doc Title", "page_numbers": [3, 4]},
        ),
    ]

    await summarizer.summarize("Query", chunks)
    sys_content = llm.calls[0][0].content
    assert "source=doc1.txt" in sys_content
    assert "page=10" in sys_content
    assert "source=Doc Title" in sys_content
    assert "page=3, 4" in sys_content


@pytest.mark.asyncio
async def test_targeted_summarizer_context_slicing() -> None:
    llm = MockLLM("Summary")
    # Small character limit: only first chunk should fully fit
    summarizer = TargetedSummarizer(llm=cast(Any, llm), model_name="gpt-4o-mini", max_context_chars=200)

    chunks = [
        RetrievedChunk(
            knowledge_base_id=uuid4(),
            doc_id=str(uuid4()),
            chunk_id=str(uuid4()),
            score=0.95,
            vector_score=0.95,
            content="Short content",
            metadata={"source": "doc.pdf"},
        ),
        RetrievedChunk(
            knowledge_base_id=uuid4(),
            doc_id=str(uuid4()),
            chunk_id=str(uuid4()),
            score=0.90,
            vector_score=0.90,
            content="This is a very long content that will exceed the remaining character budget.",
            metadata={"source": "doc.pdf"},
        ),
    ]

    await summarizer.summarize("Query", chunks)
    sys_content = llm.calls[0][0].content
    assert "Short content" in sys_content
    # The second chunk shouldn't be fully included or might be sliced/skipped
    # Let's verify that the character limit is respected
    assert len(sys_content) <= 200 + len(
        "You are a retrieval-augmented assistant. Use the knowledge-base context below as the primary evidence. If the context is insufficient, say so instead of inventing details. Cite relevant chunks with bracketed source numbers like [cite:1].\n\nKnowledge-base context:\n"
    )
