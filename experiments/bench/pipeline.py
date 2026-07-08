"""Real (non-mock) in-process RAG pipeline for the config sweep benchmark.

Composes `rag-core` primitives directly — no backend, worker, or LangGraph.
Only external services required: Qdrant (vectors) + LiteLLM (embeddings/LLM/rerank).
Parser services (docling :15001, fast-parser :15002) are needed only for the
corresponding parser providers.

The config sweep axes live in `PipelineConfig`:
  (a) parser            -> ingest-time  (docling|pymupdf4llm|pdf_oxide|native_text)
  (b) chunk / context   -> ingest-time  (chunk_size, contextual_retrieval)
  (c) retrieval_mode    -> ingest-time  (dense|sparse|hybrid; distinct collection)
  (d) rerank            -> query-time
  (e) expand_query      -> query-time

Each named config maps to a stable knowledge-base UUID; retrieval is partitioned
by that UUID's metadata filter, so multiple configs can safely share a physical
collection (the collection is keyed only by the embedding config hash).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from qdrant_client.http import models as qmodels

from rag_core.adapters.parser.instance import parse_file
from rag_core.adapters.vector_store.config import get_vector_db_settings
from rag_core.adapters.vector_store.instance import get_vector_store_provider, setup_vector_store_provider
from rag_core.ai.models import get_llm_model
from rag_core.chunkers.schemas import ChunkingConfig
from rag_core.chunkers.semantic import chunk_document
from rag_core.embeddings.indexing import chunks_to_langchain_documents, get_knowledge_vector_store
from rag_core.embeddings.schemas import KnowledgeEmbeddingConfig, resolve_knowledge_embedding_config
from rag_core.retrieval.schemas import RerankerConfig, RetrievedChunk
from rag_core.retrieval.search import retrieve_multi_knowledge_chunks

PipelineCallable = Callable[[str], Awaitable[dict]]

# Model aliases verified to actually complete requests through the LiteLLM proxy.
# (gpt-4o / text-embedding-3-small are listed but lack upstream keys — they 500.)
DEFAULT_EMBEDDING_MODEL = "vllm-embedding"  # 1024-dim, reachable
DEFAULT_LLM_MODEL = "gpt-oss-20b"
DEFAULT_RERANKER_MODEL = "vllm-reranker"


@dataclass(frozen=True)
class PipelineConfig:
    """One point in the benchmark sweep space."""

    name: str
    parser: str = "pymupdf4llm"
    retrieval_mode: str = "hybrid"
    sparse_model: str | None = "en-bm25"
    rerank: bool = False
    contextual_retrieval: bool = False
    expand_query: bool = False
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    llm_model: str = DEFAULT_LLM_MODEL
    reranker_model: str = DEFAULT_RERANKER_MODEL
    limit: int = 5
    chunk_size: int = 450
    chunk_overlap: int = 50

    @property
    def kb_id(self) -> UUID:
        """Stable knowledge-base UUID derived from the config name."""
        return uuid5(NAMESPACE_URL, f"rag-bench:{self.name}")

    def embedding_config(self) -> KnowledgeEmbeddingConfig:
        sparse = self.sparse_model if self.retrieval_mode in ("sparse", "hybrid") else None
        return resolve_knowledge_embedding_config(
            {
                "model": self.embedding_model,
                "retrieval_mode": self.retrieval_mode,
                "sparse_model": sparse,
            }
        )

    def chunking_config(self) -> ChunkingConfig:
        return ChunkingConfig(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            enable_contextual_retrieval=self.contextual_retrieval,
            contextual_retrieval_model=self.llm_model if self.contextual_retrieval else None,
        )


_PROVIDER_INITIALIZED = False


async def ensure_provider() -> None:
    """Initialize the global vector-store provider once per process."""
    global _PROVIDER_INITIALIZED
    if not _PROVIDER_INITIALIZED:
        await setup_vector_store_provider(get_vector_db_settings())
        _PROVIDER_INITIALIZED = True


async def _wipe_kb(collection: str, kb_id: UUID) -> None:
    """Delete all previously-indexed points for a knowledge base (idempotent re-ingest)."""
    provider = get_vector_store_provider()
    await provider.delete_points(
        collection_name=collection,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="metadata.knowledge_id",
                        match=qmodels.MatchValue(value=str(kb_id)),
                    )
                ]
            )
        ),
    )


async def ingest_corpus(pdf_paths: list[Path], config: PipelineConfig, *, wipe: bool = False) -> UUID:
    """Parse -> chunk -> embed each PDF into the config's knowledge base. Returns the kb_id."""
    await ensure_provider()
    kb_id = config.kb_id
    emb = config.embedding_config()
    chunk_cfg = config.chunking_config()
    store, collection, _ = await get_knowledge_vector_store(emb)
    logger.info(f"[{config.name}] ingest -> collection={collection} kb_id={kb_id}")
    if wipe:
        await _wipe_kb(collection, kb_id)

    total_chunks = 0
    for path in pdf_paths:
        content = path.read_bytes()
        parsed = await parse_file(
            content,
            filename=path.name,
            content_type="application/pdf",
            provider=config.parser,
        )
        chunks = chunk_document(parsed, config=chunk_cfg)
        docs = chunks_to_langchain_documents(chunks, knowledge_base_id=kb_id)
        # Stamp the source filename so retrieval metrics can match on doc regardless of parser.
        for doc in docs:
            doc.metadata["source_doc"] = path.name
        if docs:
            await store.aadd_documents(docs)
        total_chunks += len(docs)
        logger.info(f"[{config.name}] {path.name}: {len(docs)} chunks")

    logger.info(f"[{config.name}] ingest complete: {total_chunks} chunks from {len(pdf_paths)} docs")
    return kb_id


_ANSWER_SYSTEM_PROMPT = """You are a precise question-answering assistant.
Answer the user's question using ONLY the numbered context passages below.
If the answer is not in the context, say you don't have enough information.
Cite the passages you use with their bracket numbers, e.g. [1], [2].

Context:
{context}"""


def _format_contexts(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(f"[{i + 1}] {c.content}" for i, c in enumerate(chunks))


def _extract_text(content: object) -> str:
    """Extract the answer text from an LLM response.

    Reasoning models (e.g. gpt-oss) return `content` as a list of blocks mixing
    `{"type": "thinking", ...}` with `{"type": "text", ...}`; we keep only the
    visible text and drop the chain-of-thought.
    """
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") in ("text", None):
                parts.append(str(block.get("text", "")))
        return "".join(parts).strip()
    return str(content).strip()


def make_pipeline(config: PipelineConfig) -> PipelineCallable:
    """Build the `async pipeline(question) -> {answer, contexts, chunks}` callable for a config."""
    emb = config.embedding_config()
    reranker = RerankerConfig(model=config.reranker_model) if config.rerank else None
    llm = get_llm_model(config.llm_model, max_tokens=2000)
    kb_id = config.kb_id

    async def pipeline(question: str) -> dict:
        await ensure_provider()
        queries: list[str] = [question]
        # (e) expand_query is applied by the caller-facing sweep; kept simple here.

        chunks = await retrieve_multi_knowledge_chunks(
            query=queries,
            kb_configs=[(kb_id, emb)],
            limit=config.limit,
            reranker_config=reranker,
        )

        system = SystemMessage(_ANSWER_SYSTEM_PROMPT.format(context=_format_contexts(chunks)))
        response = await llm.ainvoke([system, HumanMessage(content=question)])
        answer = _extract_text(response.content)

        return {
            "answer": answer,
            "contexts": [c.content for c in chunks],
            "chunks": chunks,  # full objects for retrieval-metric (doc/page) matching
        }

    return pipeline


async def _smoke() -> None:
    """End-to-end smoke test: ingest one PDF, run one query, print the result."""
    config = PipelineConfig(name="smoke", parser="pymupdf4llm", retrieval_mode="dense")
    pdf = Path(__file__).resolve().parents[2] / "datasets" / "pdfs" / "2010-k_page85.pdf"
    assert pdf.exists(), f"missing test pdf: {pdf}"

    kb_id = await ingest_corpus([pdf], config)
    pipeline = make_pipeline(config)
    result = await pipeline("What is this document about? Summarize the key financial points.")

    print("\n" + "=" * 60)
    print("SMOKE TEST RESULT")
    print("=" * 60)
    print(f"kb_id: {kb_id}")
    print(f"contexts retrieved: {len(result['contexts'])}")
    print(f"\nANSWER:\n{result['answer'][:800]}")
    print("\nFIRST CONTEXT (200 chars):")
    print((result["contexts"][0][:200] if result["contexts"] else "<none>"))
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(_smoke())
