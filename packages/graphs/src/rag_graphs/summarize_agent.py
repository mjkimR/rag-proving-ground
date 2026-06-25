"""Aegra-served LangGraph entrypoint for Document Summarization Agent."""

import asyncio
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, MessagesState, StateGraph
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field
from rag_core.ai.models import get_llm_model
from rag_core.retrieval import RerankerConfig
from rag_core.summarize import TargetedSummarizer, TreeSummarizer
from typing_extensions import TypedDict

from rag_graphs.util.backend import (
    get_document_chunks,
    get_session_attachments,
    search_multi_knowledge_bases,
)
from rag_graphs.util.messages import message_content, sanitize_messages_for_llm

DEFAULT_RETRIEVAL_LIMIT = 5
DEFAULT_MAX_CONTEXT_CHARS = 16_000


class AttachmentStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SummarizeConfig(TypedDict, total=False):
    model_name: str | None
    limit: int
    candidate_limit: int | None
    reranker_config: dict[str, Any] | None
    max_context_chars: int
    retrieval_mode: str | None
    sparse_model: str | None
    rewrite_mode: str | None
    language: str


class _GraphRuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model_name: str | None = None
    limit: int = Field(default=DEFAULT_RETRIEVAL_LIMIT, ge=1, le=100)
    candidate_limit: int | None = Field(default=None, ge=1, le=500)
    reranker_config: RerankerConfig | None = None
    max_context_chars: int = Field(default=DEFAULT_MAX_CONTEXT_CHARS, ge=1, le=200_000)
    retrieval_mode: str | None = None
    sparse_model: str | None = None
    rewrite_mode: str | None = None
    language: str = "en"


class SummarizeState(MessagesState, total=False):
    intent: Literal["TREE", "RAG", "CHAT", "ERROR"]
    doc_ids: list[str]
    kb_id: str | None
    failed_filenames: list[str]
    error_message: str | None


def _runtime_config(config: RunnableConfig) -> _GraphRuntimeConfig:
    return _GraphRuntimeConfig.model_validate(config.get("configurable", {}))


def _last_human_query(messages: list[Any]) -> str | None:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            content = message_content(message).strip()
            return content or None
        if isinstance(message, dict) and message.get("type") in {"human", "user"}:
            content = str(message.get("content") or "").strip()
            return content or None
    return None


async def safety_gate(state: SummarizeState, config: RunnableConfig) -> dict[str, Any]:
    """Safety Gate: Checks the processing status of session attachments.

    Fails fast if any attachment is still processing.
    """
    thread_id = config.get("configurable", {}).get("thread_id")
    if not thread_id:
        logger.error("No thread_id found in configurable context.")
        return {
            "intent": "ERROR",
            "error_message": "Error: thread_id was not provided in configurable context.",
        }

    try:
        attachments = await get_session_attachments(thread_id)
    except Exception as e:
        logger.error(f"Failed to fetch session attachments from backend: {e}")
        return {
            "intent": "ERROR",
            "error_message": f"Error: Failed to fetch session attachments. Detail: {e}",
        }

    if not attachments:
        return {
            "intent": "ERROR",
            "error_message": "No attachments available for summarization.",
        }

    # Early exit if any attachment is currently processing/pending
    processing_files = [
        att.get("processed_metadata", {}).get("filename") or "Unknown file"
        for att in attachments
        if att.get("status") in {AttachmentStatus.PENDING, AttachmentStatus.PROCESSING}
    ]

    if processing_files:
        files_str = ", ".join(processing_files)
        return {
            "intent": "ERROR",
            "error_message": f"Document processing is in progress. Please try again in a moment. (Pending files: {files_str})",
        }

    completed_doc_ids = []
    kb_id = None
    failed_filenames = []

    for att in attachments:
        status = att.get("status")
        meta = att.get("processed_metadata") or {}
        filename = meta.get("filename") or "Unknown file"
        if status == AttachmentStatus.COMPLETED:
            doc_id = meta.get("doc_id")
            if doc_id:
                completed_doc_ids.append(doc_id)
            if not kb_id:
                kb_id = meta.get("knowledge_base_id")
        elif status == AttachmentStatus.FAILED:
            failed_filenames.append(filename)

    if not completed_doc_ids:
        # All failed or missing metadata
        return {
            "intent": "ERROR",
            "error_message": "No successfully processed attachments found. Please check your files.",
        }

    return {
        "doc_ids": completed_doc_ids,
        "kb_id": kb_id,
        "failed_filenames": failed_filenames,
    }


async def route_intent(state: SummarizeState, config: RunnableConfig) -> dict[str, Any]:
    """Intent Router: Classify the user query into TREE, RAG, or CHAT."""
    if state.get("intent") == "ERROR":
        return {}

    query = _last_human_query(state.get("messages", []))
    if not query:
        return {"intent": "CHAT"}

    runtime_config = _runtime_config(config)
    llm = get_llm_model(runtime_config.model_name)

    router_prompt = (
        "You are an intent router. Analyze the user's latest query and classify it into one of the following categories:\n"
        "1. 'TREE': The user wants a general, high-level summary of the entire document or documents. (e.g., 'Summarize this file', 'Give me an overview of the document', 'Summarize')\n"
        "2. 'RAG': The user has a specific, targeted question or wants to summarize a specific part of the document. (e.g., 'What is the revenue in 2024?', 'Summarize the financial section only', 'Summarize the financial section only')\n"
        "3. 'CHAT': The query is not related to summarizing or querying the document contents. (e.g., 'Hello', 'Tell me a joke', 'Hi')\n\n"
        f"User Query: {query}\n\n"
        "Respond ONLY with one of the following words: TREE, RAG, or CHAT."
    )

    try:
        response = await llm.ainvoke([SystemMessage(content=router_prompt)])
        content = message_content(response).strip().upper()
        if "TREE" in content:
            intent = "TREE"
        elif "RAG" in content:
            intent = "RAG"
        else:
            intent = "CHAT"
    except Exception as e:
        logger.warning(f"Failed to route intent via LLM: {e}. Defaulting to RAG.")
        intent = "RAG"

    logger.info(f"Intent classified as: {intent} for query: '{query}'")
    return {"intent": intent}


def _append_failure_prefix(summary: str, failed_filenames: list[str]) -> str:
    """Helper to prepend a warning message if some files failed to read/process."""
    if failed_filenames:
        failed_list = ", ".join(failed_filenames)
        return f"⚠️ Some files ({failed_list}) could not be read and were excluded from the summary.\n\n" + summary
    return summary


async def tree_summarize(state: SummarizeState, config: RunnableConfig) -> dict[str, Any]:
    """Execute hierarchical tree summarization over all document chunks."""
    query = _last_human_query(state.get("messages", [])) or "Summarize the text."
    runtime_config = _runtime_config(config)
    doc_ids = state.get("doc_ids", [])

    # Parallel chunk fetching
    tasks = [get_document_chunks(UUID(doc_id)) for doc_id in doc_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_chunks = []
    for res in results:
        if isinstance(res, Exception):
            logger.error(f"Failed to fetch chunks due to an exception: {res}")
        elif isinstance(res, dict):
            all_chunks.extend(res.get("chunks", []))
        else:
            logger.error(f"Unexpected response format: {res}")

    if not all_chunks:
        return {"messages": [AIMessage(content="No text data found in the document to summarize.")]}

    llm = get_llm_model(runtime_config.model_name)
    summarizer = TreeSummarizer(
        llm=llm,
        model_name=runtime_config.model_name,
        language=runtime_config.language,
    )

    try:
        summary = await summarizer.summarize_chunks(all_chunks, query=query)
    except Exception as e:
        logger.error(f"Tree summarization failed: {e}")
        return {"messages": [AIMessage(content=f"An error occurred during tree summarization. Detail: {e}")]}

    # Prepend partial failure notice if any
    failed_filenames = state.get("failed_filenames", [])
    summary = _append_failure_prefix(summary, failed_filenames)

    return {"messages": [AIMessage(content=summary)]}


async def rag_summarize(state: SummarizeState, config: RunnableConfig) -> dict[str, Any]:
    """Execute targeted RAG synthesis using retrieved chunks."""
    query = _last_human_query(state.get("messages", []))
    if not query:
        return {"messages": [AIMessage(content="Cannot summarize because the query is empty.")]}

    runtime_config = _runtime_config(config)
    kb_id = state.get("kb_id")

    if not kb_id:
        return {"messages": [AIMessage(content="Temporary knowledge base mapping not found.")]}

    # Retrieve context chunks from Qdrant via backend search API
    try:
        chunks = await search_multi_knowledge_bases(
            queries=[query],
            knowledge_base_ids=[UUID(kb_id)],
            limit=runtime_config.limit,
            reranker_config=runtime_config.reranker_config,
            candidate_limit=runtime_config.candidate_limit,
            retrieval_mode=runtime_config.retrieval_mode,
            sparse_model=runtime_config.sparse_model,
        )
    except Exception as e:
        logger.error(f"RAG search failed: {e}")
        return {"messages": [AIMessage(content=f"An error occurred during RAG retrieval. Detail: {e}")]}

    llm = get_llm_model(runtime_config.model_name)
    summarizer = TargetedSummarizer(llm=llm, model_name=runtime_config.model_name)

    try:
        summary = await summarizer.summarize(query, chunks)
    except Exception as e:
        logger.error(f"Targeted summarization failed: {e}")
        return {"messages": [AIMessage(content=f"An error occurred during targeted summarization. Detail: {e}")]}

    # Add reference objects to AIMessage additional_kwargs (same pattern as simple_rag.py)
    references = []
    for index, chunk in enumerate(chunks, start=1):
        source = (
            chunk.metadata.get("source")
            or chunk.metadata.get("filename")
            or chunk.metadata.get("title")
            or "Unknown Source"
        )
        page = chunk.metadata.get("page") or chunk.metadata.get("page_number")
        references.append(
            {
                "index": index,
                "knowledge_base_id": str(chunk.knowledge_base_id),
                "doc_id": str(chunk.doc_id),
                "chunk_id": str(chunk.chunk_id),
                "score": float(chunk.score),
                "rerank_score": float(chunk.rerank_score) if chunk.rerank_score is not None else None,
                "content": chunk.content,
                "page_content": chunk.page_content,
                "source": source,
                "page": page,
            }
        )

    # Prepend partial failure notice if any
    failed_filenames = state.get("failed_filenames", [])
    summary = _append_failure_prefix(summary, failed_filenames)

    response = AIMessage(content=summary)
    response.additional_kwargs = {"references": references}

    return {"messages": [response]}


async def respond_chat(state: SummarizeState, config: RunnableConfig) -> dict[str, Any]:
    """Fallback: Simple chat response when no document context query is triggered."""
    runtime_config = _runtime_config(config)
    llm = get_llm_model(runtime_config.model_name)
    messages = sanitize_messages_for_llm(state.get("messages", []))

    try:
        response = await llm.ainvoke(messages, config=config)
    except Exception as e:
        logger.error(f"Chat execution failed: {e}")
        return {"messages": [AIMessage(content=f"An error occurred while generating the chat response. Detail: {e}")]}

    if not isinstance(response, AIMessage):
        response = AIMessage(content=message_content(response))

    return {"messages": [response]}


async def respond_error(state: SummarizeState, config: RunnableConfig) -> dict[str, Any]:
    """Return error message from safety gate or setup."""
    error_msg = state.get("error_message") or "An error occurred."
    return {"messages": [AIMessage(content=error_msg)]}


def route_decision(
    state: SummarizeState,
) -> Literal["tree_summarize", "rag_summarize", "respond_chat", "respond_error"]:
    """Conditional edge decision function based on intent routing."""
    routing_map: dict[str, Literal["tree_summarize", "rag_summarize", "respond_chat", "respond_error"]] = {
        "ERROR": "respond_error",
        "TREE": "tree_summarize",
        "RAG": "rag_summarize",
    }
    return routing_map.get(state.get("intent", "CHAT"), "respond_chat")


# Graph Definition
builder = StateGraph(SummarizeState, context_schema=SummarizeConfig)

# Register nodes
builder.add_node("safety_gate", safety_gate)
builder.add_node("route_intent", route_intent)
builder.add_node("tree_summarize", tree_summarize)
builder.add_node("rag_summarize", rag_summarize)
builder.add_node("respond_chat", respond_chat)
builder.add_node("respond_error", respond_error)

# Setup edges
builder.add_edge(START, "safety_gate")
builder.add_edge("safety_gate", "route_intent")

# Route dynamically based on the intent
builder.add_conditional_edges(
    "route_intent",
    route_decision,
    {
        "tree_summarize": "tree_summarize",
        "rag_summarize": "rag_summarize",
        "respond_chat": "respond_chat",
        "respond_error": "respond_error",
    },
)

# Connect everything to END
builder.add_edge("tree_summarize", END)
builder.add_edge("rag_summarize", END)
builder.add_edge("respond_chat", END)
builder.add_edge("respond_error", END)

graph = builder.compile()
