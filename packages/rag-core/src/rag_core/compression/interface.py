from collections.abc import Sequence
from typing import Any, Protocol

from rag_core.retrieval.schemas import RetrievedChunk


class ContextCompressor(Protocol):
    """Protocol for hybrid context compression pipeline components."""

    async def compress(
        self,
        query: str,
        chunks: Sequence[RetrievedChunk],
        **kwargs: Any,
    ) -> list[RetrievedChunk]:
        """Compress the retrieved chunks to reduce token usage and improve relevance.

        Args:
            query: The search query string.
            chunks: A sequence of RetrievedChunk instances to compress or filter.
            **kwargs: Additional parameters (like API limits, top_n) depending on the implementation.

        Returns:
            A list of compressed RetrievedChunk instances.
        """
        ...
