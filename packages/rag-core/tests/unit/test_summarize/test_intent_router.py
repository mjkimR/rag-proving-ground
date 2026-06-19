from typing import Any

import pytest
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable
from rag_core.summarize.intent_router import (
    IntentClassification,
    SummarizeIntentClassifier,
    SummarizeStrategy,
)


class MockLLM(Runnable):
    """A mock LLM class that mimics LangChain's BaseChatModel or Runnable."""

    def __init__(self, response_content: Any, has_structured: bool = True) -> None:
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
async def test_intent_classifier_structured_full_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. Structured output path returning IntentClassification with FULL_TREE
    mock_response = IntentClassification(strategy=SummarizeStrategy.FULL_TREE)
    mock_llm = MockLLM(mock_response, has_structured=True)

    monkeypatch.setattr("rag_core.summarize.intent_router.get_llm_model", lambda model_name: mock_llm)

    classifier = SummarizeIntentClassifier(model_name="mock-model")
    strategy = await classifier.classify("Give me a summary of the whole report.")
    assert strategy == SummarizeStrategy.FULL_TREE


@pytest.mark.asyncio
async def test_intent_classifier_structured_targeted_rag(monkeypatch: pytest.MonkeyPatch) -> None:
    # 2. Structured output path returning IntentClassification with TARGETED_RAG
    mock_response = IntentClassification(strategy=SummarizeStrategy.TARGETED_RAG)
    mock_llm = MockLLM(mock_response, has_structured=True)

    monkeypatch.setattr("rag_core.summarize.intent_router.get_llm_model", lambda model_name: mock_llm)

    classifier = SummarizeIntentClassifier(model_name="mock-model")
    strategy = await classifier.classify("What is the exact revenue of department X?")
    assert strategy == SummarizeStrategy.TARGETED_RAG


@pytest.mark.asyncio
async def test_intent_classifier_structured_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    # 3. Structured output path returning raw dict
    mock_response = {"strategy": "FULL_TREE"}
    mock_llm = MockLLM(mock_response, has_structured=True)

    monkeypatch.setattr("rag_core.summarize.intent_router.get_llm_model", lambda model_name: mock_llm)

    classifier = SummarizeIntentClassifier(model_name="mock-model")
    strategy = await classifier.classify("Outline the main chapters of the text.")
    assert strategy == SummarizeStrategy.FULL_TREE


@pytest.mark.asyncio
async def test_intent_classifier_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    # 4. Fallback text output path when structured output is not supported
    # Fallback prompt returns the text "FULL_TREE"
    mock_llm = MockLLM("FULL_TREE", has_structured=False)

    monkeypatch.setattr("rag_core.summarize.intent_router.get_llm_model", lambda model_name: mock_llm)

    classifier = SummarizeIntentClassifier(model_name="mock-model")
    strategy = await classifier.classify("Provide a high level outline of the paper.")
    assert strategy == SummarizeStrategy.FULL_TREE


@pytest.mark.asyncio
async def test_intent_classifier_fallback_default(monkeypatch: pytest.MonkeyPatch) -> None:
    # 5. Fallback fails completely, returns default strategy TARGETED_RAG
    mock_llm = MockLLM("invalid_response", has_structured=False)

    monkeypatch.setattr("rag_core.summarize.intent_router.get_llm_model", lambda model_name: mock_llm)

    classifier = SummarizeIntentClassifier(model_name="mock-model")
    strategy = await classifier.classify("Tell me about gravity.")
    assert strategy == SummarizeStrategy.TARGETED_RAG
