import asyncio
from typing import Any, cast
from uuid import UUID

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import MessagesState
from rag_core.retrieval import RetrievedChunk
from rag_graphs.simple_rag import graph
from rag_graphs.util import backend as backend_util

KB_ID = UUID("11111111-1111-1111-1111-111111111111")
SECOND_KB_ID = UUID("22222222-2222-2222-2222-222222222222")


async def test_simple_rag_retrieves_context_and_injects_system_message(mocker):
    mock_options = mocker.patch("rag_graphs.simple_rag.get_model_options")
    mock_options.return_value = {
        "llm_models": ["allowed-model"],
        "embedding_models": [],
        "reranker_models": [],
    }
    mock_search = mocker.patch("rag_graphs.simple_rag.search_multi_knowledge_bases")
    mock_search.return_value = [
        RetrievedChunk(
            chunk_id="chunk-1",
            doc_id="doc-1",
            content="RAG combines retrieval with generation.",
            score=0.91,
            knowledge_base_id=KB_ID,
            vector_score=0.91,
            metadata={"source": "rag.md", "page": 3},
        )
    ]
    mock_llm = mocker.MagicMock()
    mock_llm.ainvoke = mocker.AsyncMock(return_value=AIMessage(content="RAG answer"))
    mock_get_llm = mocker.patch("rag_graphs.simple_rag.get_llm_model")
    mock_get_llm.return_value = mock_llm

    config = cast(
        RunnableConfig,
        {
            "configurable": {
                "model_name": "allowed-model",
                "knowledge_base_ids": [str(KB_ID)],
                "limit": 3,
            }
        },
    )
    state = cast(MessagesState, {"messages": [HumanMessage(content="What is RAG?")]})

    result = await graph.ainvoke(state, config=config)

    mock_get_llm.assert_called_once_with("allowed-model")
    mock_search.assert_awaited_once()
    search_kwargs = mock_search.await_args.kwargs
    assert search_kwargs["queries"] == ["What is RAG?"]
    assert search_kwargs["knowledge_base_ids"] == [KB_ID]
    assert search_kwargs["limit"] == 3
    assert search_kwargs["reranker_config"] is None

    llm_messages = mock_llm.ainvoke.await_args.args[0]
    assert isinstance(llm_messages[0], SystemMessage)
    assert "RAG combines retrieval with generation." in llm_messages[0].content
    assert "[cite:1]" in llm_messages[0].content
    assert llm_messages[1].content == "What is RAG?"
    assert result["messages"][-1].content == "RAG answer"
    assert result["messages"][-1].additional_kwargs["references"] == [
        {
            "index": 1,
            "knowledge_base_id": str(KB_ID),
            "doc_id": "doc-1",
            "chunk_id": "chunk-1",
            "score": 0.91,
            "rerank_score": None,
            "content": "RAG combines retrieval with generation.",
            "page_content": None,
            "source": "rag.md",
            "page": 3,
        }
    ]


async def test_simple_rag_passes_reranker_config_for_multi_kb(mocker):
    mocker.patch("rag_graphs.simple_rag.get_model_options").return_value = {
        "llm_models": ["allowed-model"],
        "embedding_models": [],
        "reranker_models": ["rerank-model"],
    }
    mock_search = mocker.patch("rag_graphs.simple_rag.search_multi_knowledge_bases")
    mock_search.return_value = []
    mock_llm = mocker.MagicMock()
    mock_llm.ainvoke = mocker.AsyncMock(return_value=AIMessage(content="No context"))
    mocker.patch("rag_graphs.simple_rag.get_llm_model").return_value = mock_llm

    config = cast(
        RunnableConfig,
        {
            "configurable": {
                "model_name": "allowed-model",
                "knowledge_base_ids": [str(KB_ID), str(SECOND_KB_ID)],
                "limit": 4,
                "candidate_limit": 12,
                "reranker_config": {"model": "rerank-model", "top_n": 4},
            }
        },
    )
    state = cast(MessagesState, {"messages": [HumanMessage(content="Compare the documents")]})

    await graph.ainvoke(state, config=config)

    search_kwargs = mock_search.await_args.kwargs
    assert search_kwargs["knowledge_base_ids"] == [KB_ID, SECOND_KB_ID]
    assert search_kwargs["candidate_limit"] == 12
    assert search_kwargs["reranker_config"].model == "rerank-model"
    assert search_kwargs["reranker_config"].top_n == 4


async def test_simple_rag_rewrites_before_synonym_expansion(mocker, monkeypatch):
    mocker.patch("rag_graphs.simple_rag.get_model_options").return_value = {
        "llm_models": ["allowed-model"],
        "embedding_models": [],
        "reranker_models": [],
    }
    mock_search = mocker.patch("rag_graphs.simple_rag.search_multi_knowledge_bases")
    mock_search.return_value = []
    mock_llm = mocker.MagicMock()
    mock_llm.ainvoke = mocker.AsyncMock(return_value=AIMessage(content="No context"))
    mocker.patch("rag_graphs.simple_rag.get_llm_model").return_value = mock_llm

    rewrite_inputs: list[str] = []
    expand_inputs: list[str] = []
    synonym_inputs: list[str] = []
    active_synonym_expansions = 0
    max_active_synonym_expansions = 0

    class FakeQueryRewriter:
        def __init__(self, model_name: str | None) -> None:
            assert model_name == "allowed-model"

        async def rewrite(self, query: str, history: list[object]) -> str:
            rewrite_inputs.append(query)
            return "rewritten m-rag query"

        async def expand(self, query: str, num_queries: int) -> list[str]:
            expand_inputs.append(query)
            assert num_queries == 3
            return [query, "alternate m-rag query"]

    class FakeSynonymExpander:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def expand_query(self, query: str) -> str:
            nonlocal active_synonym_expansions, max_active_synonym_expansions
            synonym_inputs.append(query)
            active_synonym_expansions += 1
            max_active_synonym_expansions = max(max_active_synonym_expansions, active_synonym_expansions)
            await asyncio.sleep(0)
            active_synonym_expansions -= 1
            return f"{query} (modular rag)"

    monkeypatch.setattr("rag_core.query_rewrite.rewriter.QueryRewriter", FakeQueryRewriter)
    monkeypatch.setattr("rag_core.query_rewrite.synonym_expander.SynonymExpander", FakeSynonymExpander)

    config = cast(
        RunnableConfig,
        {
            "configurable": {
                "model_name": "allowed-model",
                "knowledge_base_ids": [str(KB_ID)],
                "rewrite_mode": "hybrid",
            }
        },
    )
    state = cast(
        MessagesState,
        {
            "messages": [
                HumanMessage(content="Tell me about retrieval."),
                AIMessage(content="Retrieval is about finding relevant context."),
                HumanMessage(content="What about m-rag?"),
            ]
        },
    )

    await graph.ainvoke(state, config=config)

    assert rewrite_inputs == ["What about m-rag?"]
    assert expand_inputs == ["rewritten m-rag query"]
    assert synonym_inputs == ["rewritten m-rag query", "alternate m-rag query"]
    assert max_active_synonym_expansions == 2
    assert mock_search.await_args.kwargs["queries"] == [
        "rewritten m-rag query (modular rag)",
        "alternate m-rag query (modular rag)",
    ]


async def test_simple_rag_requires_reranker_for_multi_kb():
    config = cast(
        RunnableConfig,
        {
            "configurable": {
                "knowledge_base_ids": [str(KB_ID), str(SECOND_KB_ID)],
            }
        },
    )
    state = cast(MessagesState, {"messages": [HumanMessage(content="Compare the documents")]})

    with pytest.raises(ValueError, match="reranker_config is required"):
        await graph.ainvoke(state, config=config)


def test_graph_backend_settings_reads_environment(monkeypatch):
    monkeypatch.setenv("RAG_BACKEND_BASE_URL", "http://backend.env")
    monkeypatch.setenv("RAG_BACKEND_TIMEOUT", "42.5")
    backend_util.get_graph_backend_settings.cache_clear()

    settings = backend_util.get_graph_backend_settings()

    assert settings.base_url == "http://backend.env"
    assert settings.timeout == 42.5
    backend_util.get_graph_backend_settings.cache_clear()


async def test_search_multi_knowledge_bases_calls_backend_search_api(mocker):
    response = mocker.MagicMock()
    response.json.return_value = {
        "query": "What is RAG?",
        "results": [
            {
                "chunk_id": "chunk-1",
                "doc_id": "doc-1",
                "content": "RAG combines retrieval with generation.",
                "score": 0.88,
                "knowledge_base_id": str(KB_ID),
                "vector_score": 0.9,
                "rerank_score": 0.88,
                "metadata": {"source": "rag.md"},
            }
        ],
        "total": 1,
    }
    response.raise_for_status = mocker.MagicMock()

    client = mocker.AsyncMock()
    client.post.return_value = response
    get_http_client = mocker.patch("rag_graphs.util.backend.get_http_client")
    get_http_client.return_value = client

    chunks = await backend_util.search_multi_knowledge_bases(
        query="What is RAG?",
        knowledge_base_ids=[KB_ID],
        limit=3,
        reranker_config=None,
        candidate_limit=None,
        settings=backend_util.GraphBackendSettings(base_url="http://backend.test/", timeout=12.0),
    )

    client.post.assert_awaited_once_with(
        "http://backend.test/api/v1/knowledge_bases/search",
        json={
            "query": "What is RAG?",
            "knowledge_base_ids": [str(KB_ID)],
            "limit": 3,
        },
        timeout=12.0,
    )
    assert chunks == [
        RetrievedChunk(
            chunk_id="chunk-1",
            doc_id="doc-1",
            content="RAG combines retrieval with generation.",
            score=0.88,
            knowledge_base_id=KB_ID,
            vector_score=0.9,
            rerank_score=0.88,
            metadata={"source": "rag.md"},
        )
    ]


async def test_simple_rag_resilient_synonym_expansion(mocker, monkeypatch):
    mocker.patch("rag_graphs.simple_rag.get_model_options").return_value = {
        "llm_models": ["allowed-model"],
        "embedding_models": [],
        "reranker_models": [],
    }
    mock_search = mocker.patch("rag_graphs.simple_rag.search_multi_knowledge_bases")
    mock_search.return_value = []
    mock_llm = mocker.MagicMock()
    mock_llm.ainvoke = mocker.AsyncMock(return_value=AIMessage(content="No context"))
    mocker.patch("rag_graphs.simple_rag.get_llm_model").return_value = mock_llm

    synonym_inputs: list[str] = []

    class FakeSynonymExpander:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def expand_query(self, query: str) -> str:
            synonym_inputs.append(query)
            if "fail" in query:
                raise RuntimeError("simulated expansion failure")
            return f"{query} (expanded)"

    monkeypatch.setattr("rag_core.query_rewrite.synonym_expander.SynonymExpander", FakeSynonymExpander)

    class FakeQueryRewriter:
        def __init__(self, model_name: str | None) -> None:
            pass

        async def expand(self, query: str, num_queries: int) -> list[str]:
            return ["success-query", "fail-query"]

    monkeypatch.setattr("rag_core.query_rewrite.rewriter.QueryRewriter", FakeQueryRewriter)

    config = cast(
        RunnableConfig,
        {
            "configurable": {
                "model_name": "allowed-model",
                "knowledge_base_ids": [str(KB_ID)],
                "rewrite_mode": "expand",
            }
        },
    )
    state = cast(
        MessagesState,
        {
            "messages": [
                HumanMessage(content="Test query"),
            ]
        },
    )

    await graph.ainvoke(state, config=config)

    assert set(synonym_inputs) == {"success-query", "fail-query"}
    # The failed query should remain unchanged ("fail-query")
    # The successful query should be expanded ("success-query (expanded)")
    assert mock_search.await_args.kwargs["queries"] == [
        "success-query (expanded)",
        "fail-query",
    ]


async def test_simple_rag_passes_language_to_synonym_expander(mocker, monkeypatch):
    mocker.patch("rag_graphs.simple_rag.get_model_options").return_value = {
        "llm_models": ["allowed-model"],
        "embedding_models": [],
        "reranker_models": [],
    }
    mock_search = mocker.patch("rag_graphs.simple_rag.search_multi_knowledge_bases")
    mock_search.return_value = []
    mock_llm = mocker.MagicMock()
    mock_llm.ainvoke = mocker.AsyncMock(return_value=AIMessage(content="No context"))
    mocker.patch("rag_graphs.simple_rag.get_llm_model").return_value = mock_llm

    passed_language = None

    class FakeSynonymExpander:
        def __init__(self, language: str = "en", **kwargs: Any) -> None:
            nonlocal passed_language
            passed_language = language

        async def expand_query(self, query: str) -> str:
            return query

    monkeypatch.setattr("rag_core.query_rewrite.synonym_expander.SynonymExpander", FakeSynonymExpander)

    config = cast(
        RunnableConfig,
        {
            "configurable": {
                "model_name": "allowed-model",
                "knowledge_base_ids": [str(KB_ID)],
                "language": "ko",
            }
        },
    )
    state = cast(MessagesState, {"messages": [HumanMessage(content="Test query")]})

    await graph.ainvoke(state, config=config)

    assert passed_language == "ko"
