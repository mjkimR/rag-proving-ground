from typing import Any

import pytest
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable
from rag_core.query_rewrite.rewriter import ExpandedQueries, QueryRewriter
from rag_core.query_rewrite.synonym_expander import (
    SynonymExpander,
    clear_synonyms_cache,
    register_synonym_loader,
)

# =============================================================================
# SynonymExpander Tests
# =============================================================================


@pytest.mark.asyncio
async def test_synonym_expander_loading_and_matching() -> None:
    # 1. Setup mock synonyms loader
    mock_data = {
        "m-rag": ["modular rag", "모듈형 rag"],
        "llm": ["large language model"],
        "이유": ["사유", "원인"],
    }

    async def mock_loader() -> dict[str, list[str]]:
        return mock_data

    register_synonym_loader(mock_loader)
    clear_synonyms_cache()

    expander = SynonymExpander()

    # Test exact boundary match
    query_1 = "m-rag is awesome"
    res_1 = await expander.expand_query(query_1)
    assert "m-rag (modular rag, 모듈형 rag) is awesome" in res_1

    # Test case insensitive match
    query_2 = "Tell me about LLM and its features."
    res_2 = await expander.expand_query(query_2)
    assert "llm (large language model)" in res_2.lower()

    # Test Korean boundary match
    query_3 = "그렇게 판단한 이유는 무엇인가요?"
    res_3 = await expander.expand_query(query_3)
    assert "이유 (사유, 원인)" in res_3

    # Test non-boundary mismatch (should not expand)
    query_4 = "This is a m-ragged edge"
    res_4 = await expander.expand_query(query_4)
    assert "m-rag (" not in res_4

    # Test cache invalidation
    clear_synonyms_cache()
    # Modify mock loader data
    mock_data["llm"] = ["large language model", "거대언어모델"]
    res_5 = await expander.expand_query("Tell me about llm")
    assert "llm (large language model, 거대언어모델)" in res_5


# =============================================================================
# QueryRewriter Mocking & Tests
# =============================================================================


class MockLLM(Runnable):
    def __init__(self, response_content: str | Any, has_structured: bool = True) -> None:
        self.response_content = response_content
        self.has_structured = has_structured

    def invoke(self, input: Any, config: Any = None) -> BaseMessage:
        return AIMessage(content=self.response_content)

    async def ainvoke(self, input: Any, config: Any = None, **kwargs: Any) -> BaseMessage:
        return AIMessage(content=self.response_content)

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        if not self.has_structured:
            raise AttributeError("Structured output not supported")

        class MockStructuredChain(Runnable):
            def __init__(self, response: Any) -> None:
                self.response = response

            def invoke(self, input: Any, config: Any = None) -> Any:
                return self.response

            async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
                return self.response

        return MockStructuredChain(self.response_content)


@pytest.mark.asyncio
async def test_query_rewriter_rewrite(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mock get_llm_model to return MockLLM
    mock_response = "What is the capital of France?"
    mock_llm = MockLLM(mock_response)

    monkeypatch.setattr("rag_core.query_rewrite.rewriter.get_llm_model", lambda model_name: mock_llm)

    rewriter = QueryRewriter(model_name="mock-model")

    # If no history is provided, return the query directly
    original_query = "What is its capital?"
    res_no_history = await rewriter.rewrite(original_query, history=None)
    assert res_no_history == original_query

    # If history is provided, check if LLM response is returned
    history = [
        {"role": "user", "content": "I am thinking about France."},
        {"role": "assistant", "content": "France is a country in Europe."},
    ]
    res_with_history = await rewriter.rewrite(original_query, history=history)
    assert res_with_history == mock_response


@pytest.mark.asyncio
async def test_query_rewriter_expand_structured(monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. Test structured output path
    mock_structured_response = ExpandedQueries(
        queries=["What is RAG?", "How does Retrieval-Augmented Generation work?", "RAG definition"]
    )
    mock_llm = MockLLM(mock_structured_response, has_structured=True)

    monkeypatch.setattr("rag_core.query_rewrite.rewriter.get_llm_model", lambda model_name: mock_llm)

    rewriter = QueryRewriter(model_name="mock-model")
    expanded = await rewriter.expand("What is RAG?", num_queries=3)

    assert len(expanded) <= 4
    assert expanded[0] == "What is RAG?"
    assert "How does Retrieval-Augmented Generation work?" in expanded
    assert "RAG definition" in expanded


@pytest.mark.asyncio
async def test_query_rewriter_expand_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    # 2. Test fallback text output path
    mock_text_response = (
        "What is RAG?\nHow does Retrieval-Augmented Generation work?\nRAG definition\n1. What is RAG architecture?"
    )
    # has_structured = False to force fallback
    mock_llm = MockLLM(mock_text_response, has_structured=False)

    monkeypatch.setattr("rag_core.query_rewrite.rewriter.get_llm_model", lambda model_name: mock_llm)

    rewriter = QueryRewriter(model_name="mock-model")
    expanded = await rewriter.expand("What is RAG?", num_queries=3)

    assert len(expanded) <= 4
    assert expanded[0] == "What is RAG?"
    assert "How does Retrieval-Augmented Generation work?" in expanded
    assert "RAG definition" in expanded
    assert "What is RAG architecture?" in expanded
