from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from loguru import logger

from rag_core.ai.models import get_llm_model
from rag_core.config import get_litellm_settings
from rag_core.retrieval.schemas import RetrievedChunk


class TargetedSummarizer:
    """A summarizer that performs targeted RAG synthesis using retrieved context chunks."""

    llm: Runnable

    def __init__(
        self,
        model_name: str | None = None,
        llm: Runnable | None = None,
        max_context_chars: int = 16_000,
    ) -> None:
        """Initializes the TargetedSummarizer.

        Args:
            model_name: Optional explicit name of the model. If not provided and llm
              is also not provided, falls back to the default LLM from settings.
            llm: Optional pre-initialized LangChain Runnable instance.
              If not provided, automatically resolved using model_name via get_llm_model.
            max_context_chars: The maximum character count for the combined context.
        """
        # Resolve model name
        self.model_name = model_name or get_litellm_settings().default_llm_model

        # Resolve LLM
        if llm is not None:
            self.llm = llm
        else:
            self.llm = get_llm_model(self.model_name)

        self.max_context_chars = max_context_chars
        logger.info(
            f"Initialized TargetedSummarizer for model '{self.model_name}' (max_context_chars: {self.max_context_chars})"
        )

    def _extract_page(self, metadata: dict[str, Any]) -> str | int | None:
        """Extracts the page information from chunk metadata."""
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
            valid_pages = []
            for p in page_numbers:
                p_str = str(p).strip()
                if p_str:
                    valid_pages.append(p_str)
            if not valid_pages:
                return None
            return ", ".join(valid_pages)

        if isinstance(page_numbers, (str, int)):
            if isinstance(page_numbers, str) and not page_numbers.strip():
                return None
            return page_numbers

        val_str = str(page_numbers).strip()
        return val_str if val_str else None

    def _format_chunk(self, index: int, chunk: RetrievedChunk) -> str:
        """Formats a single RetrievedChunk into a structured string block."""
        metadata_bits = []
        source = chunk.metadata.get("source") or chunk.metadata.get("filename") or chunk.metadata.get("title")
        page = self._extract_page(chunk.metadata)
        if source:
            metadata_bits.append(f"source={source}")
        if page:
            metadata_bits.append(f"page={page}")
        metadata = f" {' '.join(metadata_bits)}" if metadata_bits else ""
        score = f"score={chunk.score:.4f}"
        if chunk.rerank_score is not None:
            score = f"{score} rerank_score={chunk.rerank_score:.4f}"

        return (
            f"[{index}] kb={chunk.knowledge_base_id} doc={chunk.doc_id} "
            f"chunk={chunk.chunk_id} {score}{metadata}\n"
            f"{chunk.page_content or chunk.content}"
        )

    def _format_context(self, chunks: list[RetrievedChunk]) -> str:
        """Groups and slices chunks to fit the configured max_context_chars."""
        sections: list[str] = []
        used_chars = 0

        for index, chunk in enumerate(chunks, start=1):
            raw_section = self._format_chunk(index=index, chunk=chunk)

            # Account for "\n\n" padding when joining sections
            padding = 2 if sections else 0
            remaining_chars = self.max_context_chars - (used_chars + padding)

            if remaining_chars <= 0:
                break

            if len(raw_section) > remaining_chars:
                cutoff = remaining_chars
                sliced = raw_section[:cutoff]
                last_period = sliced.rfind(".")
                last_newline = sliced.rfind("\n")
                best_break = max(last_period, last_newline)
                final_section = sliced[: best_break + 1].rstrip() if best_break > int(cutoff * 0.6) else sliced.rstrip()
            else:
                final_section = raw_section

            if not final_section:
                continue

            sections.append(final_section)
            used_chars += len(final_section) + padding

        return "\n\n".join(sections)

    def _context_system_prompt(self, chunks: list[RetrievedChunk]) -> str:
        """Generates the system prompt populated with context."""
        if not chunks:
            return (
                "You are a retrieval-augmented assistant. No knowledge-base context was retrieved for this turn. "
                "Answer from the conversation only, and say when the available information is insufficient."
            )

        context = self._format_context(chunks=chunks)
        return (
            "You are a retrieval-augmented assistant. Use the knowledge-base context below as the primary evidence. "
            "If the context is insufficient, say so instead of inventing details. Cite relevant chunks with bracketed "
            "source numbers like [cite:1].\n\n"
            f"Knowledge-base context:\n{context}"
        )

    async def summarize(self, query: str, chunks: list[RetrievedChunk]) -> str:
        """Summarizes or answers the query using the provided context chunks."""
        system_prompt = self._context_system_prompt(chunks)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=query),
        ]
        try:
            response = await self.llm.ainvoke(messages)
            if hasattr(response, "content"):
                return str(response.content).strip()
            return str(response).strip()
        except Exception as e:
            logger.error(f"Error calling LLM during targeted RAG summarization: {e}")
            raise e
