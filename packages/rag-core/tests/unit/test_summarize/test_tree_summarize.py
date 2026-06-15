from typing import Any, cast

import pytest
from rag_core.summarize.tree_summarize import TreeSummarizer


class MockLLM:
    """A minimal mock class that mimics a LangChain BaseChatModel or Runnable with ainvoke."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    async def ainvoke(self, prompt: str) -> Any:
        self.calls.append(prompt)

        class MockResponse:
            content = self.responses.pop(0) if self.responses else "Default mock summary"

        return MockResponse()


@pytest.mark.asyncio
async def test_tree_summarizer_empty_input() -> None:
    llm = MockLLM([])
    summarizer = TreeSummarizer(llm=cast(Any, llm), model_name="gpt-4o-mini")
    res = await summarizer.summarize_chunks([], "Test query")
    assert res == ""
    assert len(llm.calls) == 0


@pytest.mark.asyncio
async def test_tree_summarizer_single_chunk_no_recursion() -> None:
    # A single chunk that fits in context window should only invoke the LLM once.
    llm = MockLLM(["Final merged summary"])
    summarizer = TreeSummarizer(llm=cast(Any, llm), model_name="gpt-4o-mini", max_output_tokens=100)

    res = await summarizer.summarize_chunks(["Chunk number 1"], "Summary target")
    assert res == "Final merged summary"
    assert len(llm.calls) == 1
    assert "Chunk number 1" in llm.calls[0]
    assert "Summary target" in llm.calls[0]


@pytest.mark.asyncio
async def test_tree_summarizer_repacking_chunks() -> None:
    # Set a small context window of 200 tokens
    llm = MockLLM(["Summary 1", "Summary 2", "Final response"])
    summarizer = TreeSummarizer(
        llm=cast(Any, llm),
        model_name="gpt-4o-mini",
        max_output_tokens=50,
        safety_margin_ratio=0.0,
        safety_margin_buffer=10,
        context_window=200,
    )

    # Test packing small chunks
    # Since the budget is small, it should group them but split if they exceed the budget.
    chunks = ["Small chunk A", "Small chunk B", "Small chunk C", "Small chunk D"]
    packed = summarizer.repack_chunks(chunks, "query")
    assert len(packed) > 0


@pytest.mark.asyncio
async def test_tree_summarizer_oversized_chunk_split() -> None:
    # Set a tiny context window so that a long chunk must be split.
    llm = MockLLM(["Summary part 1", "Summary part 2", "Final response"])
    summarizer = TreeSummarizer(
        llm=cast(Any, llm),
        model_name="gpt-4o-mini",
        max_output_tokens=20,
        safety_margin_ratio=0.0,
        safety_margin_buffer=5,
        context_window=80,
    )

    # Make the oversized chunk very long (e.g. 1000 characters) so that its token count
    # is much larger than the available token limit (around 15-20)
    oversized_chunk = (
        "This is a very long string " * 40 + "that should exceed the tiny context window limit and trigger splitting."
    )
    packed = summarizer.repack_chunks([oversized_chunk], "query")
    # Should split into multiple chunks
    assert len(packed) > 1


@pytest.mark.asyncio
async def test_tree_summarizer_hierarchical_recursion() -> None:
    # We want exactly 2 blocks in Level 1, then 1 block in Level 2.
    responses = ["Summary Block A", "Summary Block B", "Final Hierarchical Response"]
    llm = MockLLM(responses)
    summarizer = TreeSummarizer(
        llm=cast(Any, llm),
        model_name="gpt-4o-mini",
        max_output_tokens=50,
        safety_margin_ratio=0.0,
        safety_margin_buffer=10,
        context_window=145,
    )

    chunks = [
        "This is a test chunk that should take about twenty tokens in the cl100k_base tokenizer space.",
        "Here is the second test chunk that also takes about twenty tokens to test hierarchical grouping.",
        "And the third test chunk of about twenty tokens to ensure the budget forces two packed blocks.",
    ]

    res = await summarizer.summarize_chunks(chunks, "Merge everything")
    assert res == "Final Hierarchical Response"
    # Level 1: 2 calls to summarize the 2 packed blocks
    # Level 2: 1 call to summarize the 2 gathered summaries
    assert len(llm.calls) == 3


def test_tree_summarizer_model_name_resolution_default() -> None:
    from rag_core.config import get_litellm_settings

    # When model_name is not passed, it should default to the setting's default_llm_model
    summarizer = TreeSummarizer(llm=cast(Any, MockLLM([])))
    assert summarizer.model_name == get_litellm_settings().default_llm_model


def test_tree_summarizer_fallback_token_counter() -> None:
    summarizer = TreeSummarizer(llm=cast(Any, MockLLM([])), model_name="custom-unknown-model")
    # Force tokenizer to None to trigger fallback path
    summarizer.tokenizer = None

    # Text containing only English: 8 chars -> 2 tokens
    english_text = "abcdefgh"
    assert summarizer._count_tokens(english_text) == 2

    # Text containing only Korean: 10 Hangul characters -> 15 tokens
    korean_text = "안녕하세요반갑습니다"
    assert summarizer._count_tokens(korean_text) == 15

    # Mixed text: 4 English (1 token) + 2 Hangul (3 tokens) -> 4 tokens
    mixed_text = "abcd안녕"
    assert summarizer._count_tokens(mixed_text) == 4


@pytest.mark.asyncio
async def test_tree_summarizer_fail_fast_compression_check() -> None:
    # If the LLM summaries are longer than or equal to the input block lengths,
    # the fail-fast check must trigger immediately and raise a ValueError.
    responses = ["A" * 500, "B" * 500]
    llm = MockLLM(responses)
    summarizer = TreeSummarizer(
        llm=cast(Any, llm),
        model_name="gpt-4o-mini",
        max_output_tokens=50,
        safety_margin_ratio=0.0,
        safety_margin_buffer=10,
        context_window=145,
    )

    chunks = [
        "This is chunk number one. It takes a modest amount of tokens and we are making it longer so that it exceeds the limit.",
        "This is chunk number two. It also takes a modest amount of tokens and we are making it longer so that it exceeds the limit.",
        "This is chunk number three. It also takes some tokens and we are making it longer so that it exceeds the limit.",
    ]

    with pytest.raises(ValueError, match=r"Summarization loop detected: Model output did not shrink the context\."):
        await summarizer.summarize_chunks(chunks, "Merge everything")
