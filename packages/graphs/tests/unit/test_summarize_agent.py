from typing import cast
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from rag_core.retrieval import RetrievedChunk
from rag_graphs.summarize_agent import SummarizeState, graph

KB_ID = UUID("11111111-1111-1111-1111-111111111111")
DOC_ID = UUID("22222222-2222-2222-2222-222222222222")


async def test_safety_gate_blocks_when_processing(mocker):
    # Mock backend session attachments to show a PENDING status file
    mock_attachments = mocker.patch("rag_graphs.summarize_agent.get_session_attachments")
    mock_attachments.return_value = [
        {
            "id": "sfa-id",
            "thread_id": "thread-1",
            "file_attachment_id": "fa-id",
            "purpose": "temp_kb",
            "status": "PENDING",
            "processed_metadata": {"filename": "busy_doc.pdf"},
        }
    ]

    config = cast(
        RunnableConfig,
        {
            "configurable": {
                "thread_id": "thread-1",
                "model_name": "mock-model",
            }
        },
    )
    state = cast(SummarizeState, {"messages": [HumanMessage(content="Summarize this")]})

    result = await graph.ainvoke(state, config=config)

    assert "in progress" in result["messages"][-1].content
    assert "busy_doc.pdf" in result["messages"][-1].content
    mock_attachments.assert_awaited_once_with("thread-1")


async def test_safety_gate_blocks_when_no_attachments(mocker):
    mock_attachments = mocker.patch("rag_graphs.summarize_agent.get_session_attachments")
    mock_attachments.return_value = []

    config = cast(
        RunnableConfig,
        {
            "configurable": {
                "thread_id": "thread-1",
                "model_name": "mock-model",
            }
        },
    )
    state = cast(SummarizeState, {"messages": [HumanMessage(content="Summarize this")]})

    result = await graph.ainvoke(state, config=config)

    assert "No attachments available" in result["messages"][-1].content


async def test_tree_summarization_path(mocker):
    # Mock safety gate checks
    mock_attachments = mocker.patch("rag_graphs.summarize_agent.get_session_attachments")
    mock_attachments.return_value = [
        {
            "id": "sfa-id",
            "thread_id": "thread-1",
            "file_attachment_id": "fa-id",
            "purpose": "temp_kb",
            "status": "COMPLETED",
            "processed_metadata": {
                "filename": "doc.pdf",
                "doc_id": str(DOC_ID),
                "knowledge_base_id": str(KB_ID),
            },
        }
    ]

    # Mock Intent Router LLM response -> classifying as TREE
    mock_llm = mocker.MagicMock()
    mock_llm.ainvoke = mocker.AsyncMock(return_value=AIMessage(content="TREE"))
    mock_get_llm = mocker.patch("rag_graphs.summarize_agent.get_llm_model")
    mock_get_llm.return_value = mock_llm

    # Mock doc chunks API
    mock_chunks = mocker.patch("rag_graphs.summarize_agent.get_document_chunks")
    mock_chunks.return_value = {
        "doc_id": str(DOC_ID),
        "total_chunks": 2,
        "chunks": ["Text chunk number one.", "Text chunk number two."],
    }

    # Mock TreeSummarizer summarization logic
    mock_tree_summarizer = mocker.MagicMock()
    mock_tree_summarizer.summarize_chunks = mocker.AsyncMock(return_value="Tree summarized content.")
    mocker.patch("rag_graphs.summarize_agent.TreeSummarizer", return_value=mock_tree_summarizer)

    config = cast(
        RunnableConfig,
        {
            "configurable": {
                "thread_id": "thread-1",
                "model_name": "mock-model",
            }
        },
    )
    state = cast(SummarizeState, {"messages": [HumanMessage(content="Summarize this document")]})

    result = await graph.ainvoke(state, config=config)

    assert result["messages"][-1].content == "Tree summarized content."
    mock_attachments.assert_awaited_once_with("thread-1")
    mock_chunks.assert_awaited_once_with(DOC_ID)
    mock_tree_summarizer.summarize_chunks.assert_awaited_once_with(
        ["Text chunk number one.", "Text chunk number two."],
        query="Summarize this document",
    )


async def test_rag_summarization_path(mocker):
    # Mock safety gate checks
    mock_attachments = mocker.patch("rag_graphs.summarize_agent.get_session_attachments")
    mock_attachments.return_value = [
        {
            "id": "sfa-id",
            "thread_id": "thread-1",
            "file_attachment_id": "fa-id",
            "purpose": "temp_kb",
            "status": "COMPLETED",
            "processed_metadata": {
                "filename": "doc.pdf",
                "doc_id": str(DOC_ID),
                "knowledge_base_id": str(KB_ID),
            },
        }
    ]

    # Mock Intent Router LLM response -> classifying as RAG
    mock_llm = mocker.MagicMock()
    mock_llm.ainvoke = mocker.AsyncMock(return_value=AIMessage(content="RAG"))
    mock_get_llm = mocker.patch("rag_graphs.summarize_agent.get_llm_model")
    mock_get_llm.return_value = mock_llm

    # Mock RAG search API call
    mock_search = mocker.patch("rag_graphs.summarize_agent.search_multi_knowledge_bases")
    mock_retrieved_chunks = [
        RetrievedChunk(
            chunk_id="chunk-1",
            doc_id=str(DOC_ID),
            content="Context from search.",
            score=0.95,
            knowledge_base_id=KB_ID,
            vector_score=0.95,
            metadata={"source": "doc.pdf"},
        )
    ]
    mock_search.return_value = mock_retrieved_chunks

    # Mock TargetedSummarizer summarization logic
    mock_targeted_summarizer = mocker.MagicMock()
    mock_targeted_summarizer.summarize = mocker.AsyncMock(return_value="RAG summarized content.")
    mocker.patch("rag_graphs.summarize_agent.TargetedSummarizer", return_value=mock_targeted_summarizer)

    config = cast(
        RunnableConfig,
        {
            "configurable": {
                "thread_id": "thread-1",
                "model_name": "mock-model",
                "limit": 3,
            }
        },
    )
    state = cast(SummarizeState, {"messages": [HumanMessage(content="Summarize the financial statements section")]})

    result = await graph.ainvoke(state, config=config)

    assert result["messages"][-1].content == "RAG summarized content."
    assert result["messages"][-1].additional_kwargs["references"][0]["content"] == "Context from search."
    mock_attachments.assert_awaited_once_with("thread-1")
    mock_search.assert_awaited_once_with(
        queries=["Summarize the financial statements section"],
        knowledge_base_ids=[KB_ID],
        limit=3,
        reranker_config=None,
        candidate_limit=None,
        retrieval_mode=None,
        sparse_model=None,
    )
    mock_targeted_summarizer.summarize.assert_awaited_once_with(
        "Summarize the financial statements section", mock_retrieved_chunks
    )
