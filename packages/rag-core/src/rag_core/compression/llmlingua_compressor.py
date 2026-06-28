import asyncio
from collections.abc import Sequence
from typing import Any

import httpx
import tiktoken
from app_http_client import get_http_client
from loguru import logger

from rag_core.config import get_llmlingua_settings
from rag_core.retrieval.schemas import RetrievedChunk

from .interface import ContextCompressor


class LLMLinguaCompressor(ContextCompressor):
    """Context Compressor using external LLMLingua service for token compression."""

    def __init__(self, max_chunks_to_process: int = 10) -> None:
        """Initialize the compressor.

        Args:
            max_chunks_to_process: Max chunks to process before batching.
        """
        self.max_chunks_to_process = max_chunks_to_process
        self.settings = get_llmlingua_settings()
        # cl100k_base is typically used for OpenAI tokenization fallback
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    async def compress(
        self,
        query: str,
        chunks: Sequence[RetrievedChunk],
        **kwargs: Any,
    ) -> list[RetrievedChunk]:
        """Compress text chunks using external LLMLingua service.

        Args:
            query: The search query.
            chunks: A sequence of RetrievedChunk instances.
            **kwargs: Ignored.

        Returns:
            A list of compressed RetrievedChunk instances.
        """
        if not chunks:
            return []

        top_chunks = list(chunks)[:self.max_chunks_to_process]
        batches = self._split_into_batches(top_chunks, max_tokens=self.settings.max_batch_tokens)

        tasks = [
            self._call_api_with_dynamic_ratio(query, batch)
            for batch in batches
        ]

        compressed_batches = await asyncio.gather(*tasks, return_exceptions=True)
        return self._merge_results(compressed_batches)

    def _split_into_batches(self, chunks: list[RetrievedChunk], max_tokens: int) -> list[list[RetrievedChunk]]:
        """Splits chunks into batches such that each batch is under max_tokens."""
        batches: list[list[RetrievedChunk]] = []
        current_batch: list[RetrievedChunk] = []
        current_tokens = 0

        for chunk in chunks:
            tokens = len(self.tokenizer.encode(chunk.content))

            # If a single chunk is larger than max_tokens, it goes in its own batch anyway
            if current_batch and current_tokens + tokens > max_tokens:
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0

            current_batch.append(chunk)
            current_tokens += tokens

        if current_batch:
            batches.append(current_batch)

        return batches

    async def _call_api_with_dynamic_ratio(self, query: str, batch: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Calls the LLMLingua API for a batch with dynamic target ratio."""
        if not batch:
            return []

        # Determine target ratio based on the average score or highest score in the batch
        max_score = max(chunk.score for chunk in batch)
        if max_score >= self.settings.high_score_threshold:
            target_ratio = self.settings.high_score_ratio
        else:
            target_ratio = self.settings.low_score_ratio

        # Prepare contexts
        contexts = [chunk.content for chunk in batch]

        payload = {
            "instruction": query,
            "context": contexts,
            "target_token_ratio": target_ratio,
        }

        client = get_http_client()
        url = f"{self.settings.base_url.rstrip('/')}/compress"

        try:
            response = await client.post(
                url,
                json=payload,
                timeout=self.settings.timeout
            )
            response.raise_for_status()
            data = response.json()

            compressed_contexts = data.get("compressed_context", [])
            # Assuming the API returns a single string with all contexts or a list
            # Usually LLMLingua returns a single string. If it returns a single string,
            # we can't easily map back. If it returns a list of strings matching the input, we map them.
            # Assuming standard LLMLingua wrapper returns a single string `compressed_context`

            # To preserve schema, we can return the first chunk with the entire compressed context
            # or try to map if it's a list. Assuming a single string response.
            if isinstance(compressed_contexts, list) and len(compressed_contexts) == len(batch):
                return [
                    chunk.model_copy(update={"content": comp_ctx})
                    for chunk, comp_ctx in zip(batch, compressed_contexts, strict=False)
                ]
            else:
                # Merge into the first chunk's identity, but this is an assumption
                # We will just update the first chunk with the entire compressed context for simplicity
                # if the API only returns a single string.
                if isinstance(compressed_contexts, str):
                    first_chunk = batch[0]
                    return [first_chunk.model_copy(update={"content": compressed_contexts})]
                elif isinstance(compressed_contexts, list) and len(compressed_contexts) > 0:
                    first_chunk = batch[0]
                    return [first_chunk.model_copy(update={"content": "\n\n".join(compressed_contexts)})]

            return batch # Fallback

        except httpx.HTTPError as e:
            logger.error(f"LLMLingua API request failed: {e}")
            return batch # Fallback to uncompressed on failure

    def _merge_results(self, compressed_batches: list[Any]) -> list[RetrievedChunk]:
        """Merges batch results, ignoring exceptions."""
        results: list[RetrievedChunk] = []
        for batch_res in compressed_batches:
            if isinstance(batch_res, Exception):
                logger.error(f"Batch processing error: {batch_res}")
                continue
            if isinstance(batch_res, list):
                results.extend(batch_res)
        return results
