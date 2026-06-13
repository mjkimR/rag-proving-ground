"""Aegra-served LangGraph entrypoint for basic knowledge-base RAG."""

from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, MessagesState, StateGraph
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from rag_core.ai.models import get_llm_model, get_model_options
from rag_core.retrieval import RerankerConfig, RetrievedChunk
from typing_extensions import TypedDict

from rag_graphs.util.backend import search_multi_knowledge_bases
from rag_graphs.util.messages import message_content, sanitize_messages_for_llm

DEFAULT_RETRIEVAL_LIMIT = 5
DEFAULT_MAX_CONTEXT_CHARS = 16_000


class KnowledgeBaseRuntimeConfig(TypedDict, total=False):
    knowledge_base_id: str
    # Backward-compatible input only. Embedding resolution is owned by the backend search API.
    embedding_config: dict[str, Any] | None


class GraphConfig(TypedDict, total=False):
    model_name: str | None
    knowledge_base_ids: list[str]
    knowledge_base_configs: list[KnowledgeBaseRuntimeConfig]
    limit: int
    candidate_limit: int | None
    reranker_config: dict[str, Any] | None
    max_context_chars: int
    retrieval_mode: str | None
    sparse_model: str | None


class _KnowledgeBaseConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    knowledge_base_id: UUID


class _GraphRuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model_name: str | None = None
    knowledge_base_ids: list[UUID] = Field(default_factory=list)
    knowledge_base_configs: list[_KnowledgeBaseConfig] = Field(default_factory=list)
    limit: int = Field(default=DEFAULT_RETRIEVAL_LIMIT, ge=1, le=100)
    candidate_limit: int | None = Field(default=None, ge=1, le=500)
    reranker_config: RerankerConfig | None = None
    max_context_chars: int = Field(default=DEFAULT_MAX_CONTEXT_CHARS, ge=1, le=200_000)
    retrieval_mode: str | None = None
    sparse_model: str | None = None

    @field_validator("knowledge_base_ids")
    @classmethod
    def dedupe_knowledge_base_ids(cls, value: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def require_reranker_for_multi_kb(self) -> "_GraphRuntimeConfig":
        if len(self.resolved_knowledge_base_ids()) >= 2 and self.reranker_config is None:
            raise ValueError("reranker_config is required when searching multiple knowledge bases.")
        if (
            self.reranker_config is not None
            and self.reranker_config.top_n is not None
            and self.reranker_config.top_n < self.limit
        ):
            raise ValueError("reranker_config.top_n must be greater than or equal to limit.")
        return self

    def resolved_knowledge_base_ids(self) -> list[UUID]:
        ids = [config.knowledge_base_id for config in self.knowledge_base_configs]
        ids.extend(self.knowledge_base_ids)
        return list(dict.fromkeys(ids))


async def respond(state: MessagesState, config: RunnableConfig) -> dict[str, list[AIMessage]]:
    runtime_config = _runtime_config(config)
    if runtime_config.model_name is not None:
        allowed = get_model_options()["llm_models"]
        if runtime_config.model_name not in allowed:
            raise ValueError(f"Unknown model '{runtime_config.model_name}'. Allowed: {allowed}")

    llm = get_llm_model(runtime_config.model_name)
    messages: list[Any] = state.get("messages", [])
    chunks = await _retrieve_context_chunks(messages=messages, runtime_config=runtime_config)
    llm_messages = _messages_with_context(
        messages=messages,
        chunks=chunks,
        max_context_chars=runtime_config.max_context_chars,
    )
    response = await llm.ainvoke(llm_messages, config=config)

    # Convert RetrievedChunk objects to serializable dicts
    references = []
    for index, chunk in enumerate(chunks, start=1):
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
                "source": chunk.metadata.get("source")
                or chunk.metadata.get("filename")
                or chunk.metadata.get("title")
                or "Unknown Source",
                "page": _extract_page(chunk.metadata),
            }
        )

    # Ensure we return an AIMessage with the references attached
    if not isinstance(response, AIMessage):
        content = message_content(response)
        response = AIMessage(content=content)
    else:
        response = response.model_copy()

    response.additional_kwargs = dict(response.additional_kwargs or {})
    response.additional_kwargs["references"] = references

    return {"messages": [response]}


def _runtime_config(config: RunnableConfig) -> _GraphRuntimeConfig:
    return _GraphRuntimeConfig.model_validate(config.get("configurable", {}))


async def _retrieve_context_chunks(
    *,
    messages: list[Any],
    runtime_config: _GraphRuntimeConfig,
) -> list[RetrievedChunk]:
    query = _last_human_query(messages)
    knowledge_base_ids = _knowledge_base_ids(runtime_config)
    if query is None or not knowledge_base_ids:
        return []

    return await search_multi_knowledge_bases(
        query=query,
        knowledge_base_ids=knowledge_base_ids,
        limit=runtime_config.limit,
        reranker_config=runtime_config.reranker_config,
        candidate_limit=runtime_config.candidate_limit,
        retrieval_mode=runtime_config.retrieval_mode,
        sparse_model=runtime_config.sparse_model,
    )


def _knowledge_base_ids(runtime_config: _GraphRuntimeConfig) -> list[UUID]:
    ids: list[UUID] = []
    seen: set[UUID] = set()

    for config in runtime_config.knowledge_base_configs:
        if config.knowledge_base_id in seen:
            continue
        seen.add(config.knowledge_base_id)
        ids.append(config.knowledge_base_id)

    for knowledge_base_id in runtime_config.knowledge_base_ids:
        if knowledge_base_id in seen:
            continue
        seen.add(knowledge_base_id)
        ids.append(knowledge_base_id)

    return ids


def _last_human_query(messages: list[Any]) -> str | None:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            content = message_content(message).strip()
            return content or None
        if isinstance(message, dict) and message.get("type") in {"human", "user"}:
            content = str(message.get("content") or "").strip()
            return content or None
    return None


def _messages_with_context(
    *,
    messages: list[Any],
    chunks: list[RetrievedChunk],
    max_context_chars: int,
) -> list[Any]:
    system_message = SystemMessage(content=_context_system_prompt(chunks=chunks, max_context_chars=max_context_chars))
    return [system_message, *sanitize_messages_for_llm(messages)]


def _context_system_prompt(*, chunks: list[RetrievedChunk], max_context_chars: int) -> str:
    if not chunks:
        return (
            "You are a retrieval-augmented assistant. No knowledge-base context was retrieved for this turn. "
            "Answer from the conversation only, and say when the available information is insufficient."
        )

    context = _format_context(chunks=chunks, max_context_chars=max_context_chars)
    return (
        "You are a retrieval-augmented assistant. Use the knowledge-base context below as the primary evidence. "
        "If the context is insufficient, say so instead of inventing details. Cite relevant chunks with bracketed "
        "source numbers like [cite:1].\n\n"
        f"Knowledge-base context:\n{context}"
    )


def _format_context(*, chunks: list[RetrievedChunk], max_context_chars: int) -> str:
    sections: list[str] = []
    used_chars = 0

    for index, chunk in enumerate(chunks, start=1):
        section = _format_chunk(index=index, chunk=chunk)
        remaining_chars = max_context_chars - used_chars
        if remaining_chars <= 0:
            break
        if len(section) > remaining_chars:
            cutoff = remaining_chars
            sliced = section[:cutoff]
            last_period = sliced.rfind(".")
            last_newline = sliced.rfind("\n")
            best_break = max(last_period, last_newline)
            section = sliced[: best_break + 1].rstrip() if best_break > int(cutoff * 0.6) else sliced.rstrip()
        sections.append(section)
        used_chars += len(section)

    return "\n\n".join(sections)


def _format_chunk(*, index: int, chunk: RetrievedChunk) -> str:
    metadata_bits = []
    source = chunk.metadata.get("source") or chunk.metadata.get("filename") or chunk.metadata.get("title")
    page = _extract_page(chunk.metadata)
    if source:
        metadata_bits.append(f"source={source}")
    if page:
        metadata_bits.append(f"page={page}")
    metadata = f" {' '.join(metadata_bits)}" if metadata_bits else ""
    score = f"score={chunk.score:.4f}"
    if chunk.rerank_score is not None:
        score = f"{score} rerank_score={chunk.rerank_score:.4f}"

    return (
        f"[{index}] kb={chunk.knowledge_base_id} doc={chunk.doc_id} chunk={chunk.chunk_id} {score}{metadata}\n"
        f"{chunk.page_content or chunk.content}"
    )


def _extract_page(metadata: dict[str, Any]) -> str | int | None:
    # Explicit None check to support 0 page number
    page_val = metadata.get("page")
    if page_val is None:
        page_val = metadata.get("page_number")

    if page_val is not None:
        if isinstance(page_val, (str, int)):
            if isinstance(page_val, str) and not page_val.strip():
                return None
            return page_val
        val_str = str(page_val).strip()
        return val_str if val_str else None

    page_numbers = metadata.get("page_numbers")
    if page_numbers is None:
        return None

    if isinstance(page_numbers, list):
        valid_pages = [str(p).strip() for p in page_numbers if str(p).strip()]
        if not valid_pages:
            return None
        return ", ".join(valid_pages)

    if isinstance(page_numbers, (str, int)):
        if isinstance(page_numbers, str) and not page_numbers.strip():
            return None
        return page_numbers

    val_str = str(page_numbers).strip()
    return val_str if val_str else None


builder = StateGraph(MessagesState, context_schema=GraphConfig)
builder.add_node("respond", respond)
builder.add_edge(START, "respond")
builder.add_edge("respond", END)

graph = builder.compile()
