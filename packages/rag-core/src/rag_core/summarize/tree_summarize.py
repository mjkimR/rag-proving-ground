import asyncio
import re

import tiktoken
from langchain_core.runnables import Runnable
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

from rag_core.ai.models import get_llm_model, get_model_metadata
from rag_core.config import get_litellm_settings

# Pre-compile Hangul character regex to avoid compilation overhead on repeated token counts
_HANGUL_PATTERN = re.compile(r"[\uac00-\ud7a3]")


class TreeSummarizer:
    """A custom, high-fidelity asynchronous hierarchical tree summarizer.

    It repacks input text chunks to fill the target model's context window,
    then recursively summarizes the chunks bottom-up in parallel.
    """

    llm: Runnable
    max_depth: int = 20

    def __init__(
        self,
        model_name: str | None = None,
        llm: Runnable | None = None,
        max_output_tokens: int = 2048,
        safety_margin_ratio: float = 0.10,
        safety_margin_buffer: int = 100,
        max_concurrency: int = 10,
        custom_prompt_template: str | None = None,
        context_window: int | None = None,
    ) -> None:
        """Initializes the TreeSummarizer.

        Args:
            model_name: Optional explicit name of the model. If not provided and llm
              is also not provided, falls back to the default LLM from settings.
            llm: Optional pre-initialized LangChain Runnable instance.
              If not provided, automatically resolved using model_name via get_llm_model.
            max_output_tokens: Number of tokens reserved for LLM generation.
              Defaults to 2048 to prevent truncation.
            safety_margin_ratio: Percentage of target size to reserve as safety padding.
              Helps absorb tokenizer differences between local counting and the remote model.
            safety_margin_buffer: Fixed token buffer added to safety margin.
            max_concurrency: Maximum number of concurrent LLM calls.
            custom_prompt_template: Custom summarization prompt template.
            context_window: Optional context window size override, useful for custom setups or tests.
        """
        # Resolve model name
        self.model_name = model_name or get_litellm_settings().default_llm_model

        # Resolve LLM
        if llm is not None:
            self.llm = llm
        else:
            self.llm = get_llm_model(self.model_name)

        self.max_output_tokens = max_output_tokens
        self.safety_margin_ratio = safety_margin_ratio
        self.safety_margin_buffer = safety_margin_buffer
        self.semaphore = asyncio.Semaphore(max_concurrency)

        # Default prompt template matching LlamaIndex style
        self.prompt_template = custom_prompt_template or (
            "You are a professional assistant tasked with summarizing documents.\n"
            "Below is a section of a document. Please provide a concise summary that answers/focuses on: {query}\n\n"
            "Content:\n{context_str}\n\n"
            "Summary:"
        )

        # Initialize tiktoken encoding
        # Try specific model encoding first, fallback to cl100k_base
        try:
            self.tokenizer = tiktoken.encoding_for_model(self.model_name)
        except Exception:
            try:
                self.tokenizer = tiktoken.get_encoding("cl100k_base")
            except Exception as e:
                logger.warning(f"Failed to load tiktoken tokenizer: {e}. Falling back to heuristic estimation.")
                self.tokenizer = None

        self.context_window = context_window or self._get_context_window()
        logger.info(
            f"Initialized TreeSummarizer for model '{self.model_name}' (context window: {self.context_window} tokens)"
        )

    def _get_context_window(self) -> int:
        """Retrieves the context window size for the active model from metadata, falling back to 128000."""
        try:
            metadata = get_model_metadata(self.model_name)
            if metadata and "context_window" in metadata:
                logger.info(
                    f"Using metadata-defined context window: {metadata['context_window']} for {self.model_name}"
                )
                return int(metadata["context_window"])
        except Exception as e:
            logger.warning(f"Could not retrieve context window from metadata for model {self.model_name}: {e}")

        # Default fallback to 128k which is the standard context size for modern LLMs
        return 128000

    def _count_tokens(self, text: str) -> int:
        """Counts the tokens in the given text using the local tokenizer."""
        if self.tokenizer is not None:
            try:
                return len(self.tokenizer.encode(text))
            except Exception:
                pass

        # Fallback to Hangul-aware conservative token counting
        # 1 Hangul character is estimated as 1.5 tokens
        # Other (ASCII/English) characters are estimated as 0.25 tokens (4 chars per token)
        hangul_chars = len(_HANGUL_PATTERN.findall(text))
        other_chars = len(text) - hangul_chars
        return int(hangul_chars * 1.5 + other_chars * 0.25)

    def _get_available_chunk_size(self, query: str) -> int:
        """Calculates available token budget for each packed chunk."""
        empty_prompt = self.prompt_template.format(query=query, context_str="")
        prompt_tokens = self._count_tokens(empty_prompt)

        available_before_margin = self.context_window - prompt_tokens - self.max_output_tokens
        if available_before_margin <= 0:
            raise ValueError(
                f"Prompt overhead ({prompt_tokens} tokens) and reserved output ({self.max_output_tokens} tokens) "
                f"exceed the model context window ({self.context_window} tokens). "
                f"Please reduce max_output_tokens or prompt size."
            )

        # Apply percentage-based + fixed buffer safety margin
        margin = int(available_before_margin * self.safety_margin_ratio) + self.safety_margin_buffer
        available = available_before_margin - margin

        if available <= 0:
            raise ValueError(
                f"Safety margin ({margin} tokens) is too large for the available space. "
                f"Please decrease safety_margin_ratio or context requirements."
            )

        return available

    def _split_large_chunk(self, chunk: str, available_tokens: int) -> list[str]:
        """Splits an oversized chunk into smaller sub-chunks that fit available token budget."""
        # 1 token is roughly 4 characters
        approx_chars = available_tokens * 4
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=approx_chars, chunk_overlap=int(approx_chars * 0.1), length_function=len
        )
        sub_chunks = splitter.split_text(chunk)

        final_sub_chunks = []
        for sc in sub_chunks:
            tokens = self._count_tokens(sc)
            if tokens <= available_tokens:
                final_sub_chunks.append(sc)
            else:
                logger.warning(f"Sub-chunk still exceeds token limit ({tokens} > {available_tokens}). Splitting again.")
                sub_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=int(approx_chars * 0.7), chunk_overlap=0, length_function=len
                )
                final_sub_chunks.extend(sub_splitter.split_text(sc))

        return final_sub_chunks

    def repack_chunks(self, text_chunks: list[str], query: str) -> list[str]:
        """Groups smaller chunks together to fully pack the model's available context window."""
        available_tokens = self._get_available_chunk_size(query)
        logger.debug(f"Repacking chunks. Target available token size per packed block: {available_tokens}")

        # 1. Preprocess: Ensure all chunks fit within available limit
        preprocessed_chunks = []
        for chunk in text_chunks:
            tokens = self._count_tokens(chunk)
            if tokens <= available_tokens:
                preprocessed_chunks.append(chunk)
            else:
                logger.info(f"Chunk exceeds available limit ({tokens} > {available_tokens} tokens). Splitting.")
                preprocessed_chunks.extend(self._split_large_chunk(chunk, available_tokens))

        # 2. Pack chunks together
        packed_chunks = []
        current_pack = []
        current_tokens = 0
        separator_tokens = self._count_tokens("\n\n")

        for chunk in preprocessed_chunks:
            chunk_tokens = self._count_tokens(chunk)
            additional_cost = chunk_tokens + (separator_tokens if current_pack else 0)

            if current_tokens + additional_cost <= available_tokens:
                current_pack.append(chunk)
                current_tokens += additional_cost
            else:
                if current_pack:
                    packed_chunks.append("\n\n".join(current_pack))
                current_pack = [chunk]
                current_tokens = chunk_tokens

        if current_pack:
            packed_chunks.append("\n\n".join(current_pack))

        logger.info(f"Repacked {len(text_chunks)} input chunks into {len(packed_chunks)} packed blocks.")
        return packed_chunks

    async def summarize_chunks(self, text_chunks: list[str], query: str = "Summarize the text.", depth: int = 0) -> str:
        """Asynchronously summarizes multiple text chunks hierarchically using a tree structure."""
        if not text_chunks:
            return ""

        if depth >= self.max_depth:
            logger.error(
                f"Tree summarization recursion depth exceeded limit (max {self.max_depth} levels). Breaking recursion."
            )
            raise ValueError("Summarization loop detected: recursion depth limit exceeded.")

        packed_blocks = self.repack_chunks(text_chunks, query)

        # Base case: 1 block left
        if len(packed_blocks) == 1:
            return await self._call_llm_for_chunk(packed_blocks[0], query)

        # Recursive case: summarize packed blocks in parallel with concurrency control
        logger.info(f"Recursive tree summary: Summarizing {len(packed_blocks)} packed blocks in parallel.")

        async def _wrapped_call(block: str) -> str:
            async with self.semaphore:
                return await self._call_llm_for_chunk(block, query)

        tasks = [_wrapped_call(block) for block in packed_blocks]
        summaries = await asyncio.gather(*tasks)

        # Fail-fast safety check to detect and prevent infinite loop when LLM fails to compress
        total_input_chars = sum(len(block) for block in packed_blocks)
        total_summary_chars = sum(len(summary) for summary in summaries)

        if total_summary_chars >= total_input_chars:
            logger.error(
                f"LLM failed to reduce text size (Input: {total_input_chars} chars, "
                f"Output: {total_summary_chars} chars). Breaking potential infinite loop early."
            )
            raise ValueError("Summarization loop detected: Model output did not shrink the context.")

        # Recurse with new summaries
        return await self.summarize_chunks(summaries, query, depth=depth + 1)

    async def summarize(self, full_text: str, query: str = "Summarize the text.") -> str:
        """Splits full_text and asynchronously summarizes it hierarchically using a tree structure."""
        # Split text into rough paragraph chunks to start with
        available_tokens = self.context_window - self.max_output_tokens
        # Apply safety margin ratio and fixed safety margin buffer
        margin = int(available_tokens * self.safety_margin_ratio) + self.safety_margin_buffer
        available_tokens -= margin
        approx_chars = available_tokens * 4

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=approx_chars // 2, chunk_overlap=approx_chars // 20, length_function=len
        )
        initial_chunks = splitter.split_text(full_text)
        return await self.summarize_chunks(initial_chunks, query)

    async def _call_llm_for_chunk(self, context_str: str, query: str) -> str:
        """Invokes the LangChain LLM model for a single chunk."""
        prompt = self.prompt_template.format(query=query, context_str=context_str)

        try:
            response = await self.llm.ainvoke(prompt)
            if hasattr(response, "content"):
                return str(response.content).strip()
            return str(response).strip()
        except Exception as e:
            err_msg = str(e).lower()
            context_err_indicators = [
                "context length",
                "context window",
                "maximum context length",
                "too long",
                "token limit",
                "maximum tokens",
                "exceeds",
            ]
            if any(indicator in err_msg for indicator in context_err_indicators):
                logger.error(f"Context window error occurred: {e}")
                raise ValueError(
                    f"Context window error occurred during LLM request. "
                    f"Please specify the correct 'context_window' size in the model's metadata "
                    f"in models.yaml (e.g., metadata: {{ role: llm, context_window: 8192 }}). "
                    f"Current configured context window size is {self.context_window}. "
                    f"Original error details: {e}"
                ) from e
            logger.error(f"Error calling LLM during summarization step: {e}")
            raise e
