import asyncio
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


class FakeVersionCache:
    def __init__(self, *, version: str | None = None) -> None:
        self.version = version
        self.get_calls: list[str] = []
        self.set_calls: list[str] = []
        self.set_values: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        self.get_calls.append(key)
        if key == "synonyms:version":
            return self.version
        raise AssertionError(f"unexpected key: {key}")

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        self.set_calls.append(key)
        self.set_values[key] = value

    async def delete(self, key: str) -> None:
        raise AssertionError("version-only cache should not delete a synonym map")


class FailingVersionCache:
    async def get(self, key: str) -> None:
        raise RuntimeError("redis unavailable")

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        raise RuntimeError("redis unavailable")


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

    # 2. English strategy tests (default)
    expander_en = SynonymExpander(language="en")

    # Test exact boundary match
    query_1 = "m-rag is awesome"
    res_1 = await expander_en.expand_query(query_1)
    assert "m-rag (modular rag, 모듈형 rag) is awesome" in res_1

    # Test case insensitive match
    query_2 = "Tell me about LLM and its features."
    res_2 = await expander_en.expand_query(query_2)
    assert "llm (large language model)" in res_2.lower()

    # Test that English strategy does NOT match Korean postpositions (due to )
    query_3 = "그렇게 판단한 이유는 무엇인가요?"
    res_3 = await expander_en.expand_query(query_3)
    assert "이유 (사유, 원인)" not in res_3

    # Test non-boundary mismatch (should not expand)
    query_4 = "This is a m-ragged edge"
    res_4 = await expander_en.expand_query(query_4)
    assert "m-rag (" not in res_4

    # 3. Korean strategy tests
    expander_ko = SynonymExpander(language="ko")

    # Test that Korean strategy correctly matches Korean postpositions
    query_ko = "그렇게 판단한 이유는 무엇인가요?"
    res_ko = await expander_ko.expand_query(query_ko)
    assert "이유 (사유, 원인)는 무엇인가요?" in res_ko

    # Test cache invalidation
    clear_synonyms_cache()
    # Modify mock loader data
    mock_data["llm"] = ["large language model", "거대언어모델"]
    res_5 = await expander_en.expand_query("Tell me about llm")
    assert "llm (large language model, 거대언어모델)" in res_5


async def test_invalidate_synonyms_cache_bumps_distributed_version(monkeypatch: pytest.MonkeyPatch) -> None:
    from rag_core.query_rewrite import synonym_expander

    fake_cache = FakeVersionCache()
    monkeypatch.setattr(synonym_expander, "_get_redis_cache_client", lambda: fake_cache)

    synonym_expander._CACHED_SYNONYMS = {"llm": ["old value"]}
    synonym_expander._IS_LOADED = True
    synonym_expander._CACHED_VERSION = "old-version"

    await synonym_expander.invalidate_synonyms_cache()

    assert synonym_expander._CACHED_SYNONYMS == {}
    assert synonym_expander._IS_LOADED is False
    assert synonym_expander._CACHED_VERSION is None
    assert set(fake_cache.set_values) == {"synonyms:version"}
    assert isinstance(fake_cache.set_values["synonyms:version"], str)
    assert fake_cache.set_values["synonyms:version"] != "old-version"


def test_redis_cache_client_uses_string_serializer(monkeypatch: pytest.MonkeyPatch) -> None:
    from aiocache.serializers import StringSerializer
    from rag_core.query_rewrite import synonym_expander

    class RedisSettings:
        url = "redis://:secret@localhost:6380/2"

    class CacheSettings:
        enabled = True
        namespace = "test-synonyms"

    monkeypatch.setattr(synonym_expander, "get_redis_settings", lambda: RedisSettings())
    monkeypatch.setattr(synonym_expander, "get_synonym_cache_settings", lambda: CacheSettings())
    monkeypatch.setattr(synonym_expander, "_REDIS_CACHE_CLIENT", None)
    monkeypatch.setattr(synonym_expander, "_REDIS_CACHE_IMPORT_FAILED", False)
    monkeypatch.setattr(synonym_expander, "_REDIS_CACHE_CONNECT_FAILED", False)

    redis_client = synonym_expander._get_redis_cache_client()

    assert redis_client is not None
    assert isinstance(redis_client.serializer, StringSerializer)


async def test_synonyms_use_local_cache_when_distributed_version_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rag_core.query_rewrite import synonym_expander

    load_calls = 0

    async def loader() -> dict[str, list[str]]:
        nonlocal load_calls
        load_calls += 1
        return {"llm": ["large language model"]}

    fake_cache = FakeVersionCache(version="version-1")
    monkeypatch.setattr(synonym_expander, "_get_redis_cache_client", lambda: fake_cache)
    register_synonym_loader(loader)
    synonym_expander.clear_synonyms_cache()

    first = await synonym_expander.get_synonyms()
    second = await synonym_expander.get_synonyms()

    assert first == {"llm": ["large language model"]}
    assert second == {"llm": ["large language model"]}
    assert fake_cache.get_calls == ["synonyms:version"]
    assert fake_cache.set_calls == []
    assert load_calls == 1


async def test_synonyms_recheck_version_without_downloading_map_after_local_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rag_core.query_rewrite import synonym_expander

    load_calls = 0

    async def loader() -> dict[str, list[str]]:
        nonlocal load_calls
        load_calls += 1
        return {"llm": ["large language model"]}

    fake_cache = FakeVersionCache(version="version-1")
    monkeypatch.setattr(synonym_expander, "_get_redis_cache_client", lambda: fake_cache)
    register_synonym_loader(loader)
    synonym_expander.clear_synonyms_cache()

    first = await synonym_expander.get_synonyms()
    synonym_expander._VERSION_CHECK_EXPIRES_AT = 0.0
    second = await synonym_expander.get_synonyms()

    assert first == {"llm": ["large language model"]}
    assert second == {"llm": ["large language model"]}
    assert fake_cache.get_calls == ["synonyms:version", "synonyms:version"]
    assert load_calls == 1


async def test_synonyms_reload_from_loader_when_redis_version_read_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rag_core.query_rewrite import synonym_expander

    load_calls = 0

    async def fresh_loader() -> dict[str, list[str]]:
        nonlocal load_calls
        load_calls += 1
        return {"llm": ["fresh db value"]}

    monkeypatch.setattr(synonym_expander, "_get_redis_cache_client", lambda: FailingVersionCache())
    register_synonym_loader(fresh_loader)

    synonym_expander._CACHED_SYNONYMS = {"llm": ["stale local value"]}
    synonym_expander._CACHED_VERSION = "old-version"
    synonym_expander._IS_LOADED = True
    synonym_expander._VERSION_CHECK_EXPIRES_AT = 0.0
    synonym_expander._LOCAL_CACHE_EXPIRES_AT = 0.0

    synonyms = await synonym_expander.get_synonyms()

    assert synonyms == {"llm": ["fresh db value"]}
    assert synonym_expander._CACHED_SYNONYMS == {"llm": ["fresh db value"]}
    assert load_calls == 1

    synonyms = await synonym_expander.get_synonyms()

    assert synonyms == {"llm": ["fresh db value"]}
    assert load_calls == 1


async def test_synonyms_redis_outage_fallback_coalesces_concurrent_loads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rag_core.query_rewrite import synonym_expander

    load_calls = 0
    release_loader = asyncio.Event()

    async def slow_loader() -> dict[str, list[str]]:
        nonlocal load_calls
        load_calls += 1
        await release_loader.wait()
        return {"llm": ["fresh db value"]}

    monkeypatch.setattr(synonym_expander, "_get_redis_cache_client", lambda: FailingVersionCache())
    register_synonym_loader(slow_loader)
    clear_synonyms_cache()

    first_task = asyncio.create_task(synonym_expander.get_synonyms())
    second_task = asyncio.create_task(synonym_expander.get_synonyms())
    await asyncio.sleep(0)

    assert load_calls == 1

    release_loader.set()
    first, second = await asyncio.gather(first_task, second_task)

    assert first == {"llm": ["fresh db value"]}
    assert second == {"llm": ["fresh db value"]}
    assert load_calls == 1


async def test_clear_synonyms_cache_clears_word_boundary_cache() -> None:
    from rag_core.query_rewrite.word_boundary import (
        _compile_english_pattern,
        _compile_korean_pattern,
    )

    # Prime the caches
    _compile_english_pattern("test1")
    _compile_korean_pattern("test2")

    assert _compile_english_pattern.cache_info().currsize > 0
    assert _compile_korean_pattern.cache_info().currsize > 0

    # Clear cache
    clear_synonyms_cache()

    # Caches should be cleared (currsize == 0)
    assert _compile_english_pattern.cache_info().currsize == 0
    assert _compile_korean_pattern.cache_info().currsize == 0


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
