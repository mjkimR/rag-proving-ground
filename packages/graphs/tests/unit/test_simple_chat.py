from typing import cast

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import MessagesState
from rag_graphs.simple_chat import graph


async def test_simple_chat_success(mocker):
    # Mock get_model_options to return our allowed models
    mock_options = mocker.patch("rag_graphs.simple_chat.get_model_options")
    mock_options.return_value = {
        "llm_models": ["gpt-oss-20b", "allowed-model"],
        "embedding_models": [],
        "reranker_models": [],
    }

    # Mock get_llm_model to return a mock LLM that returns a specific AIMessage
    mock_llm = mocker.MagicMock()
    mock_llm.ainvoke = mocker.AsyncMock(return_value=AIMessage(content="Hello from mock LLM"))
    mock_get_llm = mocker.patch("rag_graphs.simple_chat.get_llm_model")
    mock_get_llm.return_value = mock_llm

    # Invoke graph with configurable model_name
    config = cast(RunnableConfig, {"configurable": {"model_name": "allowed-model"}})
    state = cast(MessagesState, {"messages": [HumanMessage(content="Hello")]})
    result = await graph.ainvoke(state, config=config)

    # Asserts
    mock_get_llm.assert_called_once_with("allowed-model")
    mock_llm.ainvoke.assert_called_once()
    assert len(result["messages"]) == 2  # Input HumanMessage + Output AIMessage
    assert result["messages"][-1].content == "Hello from mock LLM"


async def test_simple_chat_default_model(mocker):
    # Mock get_model_options
    mock_options = mocker.patch("rag_graphs.simple_chat.get_model_options")
    mock_options.return_value = {
        "llm_models": ["gpt-oss-20b"],
        "embedding_models": [],
        "reranker_models": [],
    }

    # Mock get_llm_model
    mock_llm = mocker.MagicMock()
    mock_llm.ainvoke = mocker.AsyncMock(return_value=AIMessage(content="Hello default"))
    mock_get_llm = mocker.patch("rag_graphs.simple_chat.get_llm_model")
    mock_get_llm.return_value = mock_llm

    # Invoke graph with model_name as None
    config = cast(RunnableConfig, {"configurable": {"model_name": None}})
    state = cast(MessagesState, {"messages": [HumanMessage(content="Hello")]})
    result = await graph.ainvoke(state, config=config)

    mock_get_llm.assert_called_once_with(None)
    assert result["messages"][-1].content == "Hello default"


async def test_simple_chat_invalid_model(mocker):
    # Mock get_model_options
    mock_options = mocker.patch("rag_graphs.simple_chat.get_model_options")
    mock_options.return_value = {
        "llm_models": ["gpt-oss-20b"],
        "embedding_models": [],
        "reranker_models": [],
    }

    # Invoke graph with unallowed model_name
    config = cast(RunnableConfig, {"configurable": {"model_name": "unallowed-model"}})
    state = cast(MessagesState, {"messages": [HumanMessage(content="Hello")]})

    with pytest.raises(ValueError, match="Unknown model 'unallowed-model'"):
        await graph.ainvoke(state, config=config)
