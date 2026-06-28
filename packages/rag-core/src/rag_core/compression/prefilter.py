from collections.abc import Sequence
from typing import Any

from rag_core.retrieval.rerank import rerank_chunks
from rag_core.retrieval.schemas import RerankerConfig, RetrievedChunk

from .interface import ContextCompressor


class RerankerPrefilter(ContextCompressor):
    """Context Compressor that utilizes an external Reranker model for pre-filtering.

    This acts as the first step in the hybrid context compression pipeline,
    reducing the total number of chunks before passing them to the expensive LLM
    or LLMLingua compression phases.
    """

    def __init__(self, limit: int, reranker_config: RerankerConfig) -> None:
        """Initialize the prefilter.

        Args:
            limit: The maximum number of top chunks to return.
            reranker_config: The Reranker configuration used for scoring.
        """
        self.limit = limit
        self.reranker_config = reranker_config

    async def compress(
        self,
        query: str,
        chunks: Sequence[RetrievedChunk],
        **kwargs: Any,
    ) -> list[RetrievedChunk]:
        """Pre-filter retrieved chunks by reranking them and keeping the top `limit`.

        Args:
            query: The original search query.
            chunks: The retrieved chunks to rerank and filter.
            **kwargs: Ignored.

        Returns:
            A reduced and sorted list of RetrievedChunk objects based on reranker score.
        """
        if not chunks:
            return []

        # rerank_chunks requires a list[RetrievedChunk]
        chunks_list = list(chunks)

        return await rerank_chunks(
            query=query,
            chunks=chunks_list,
            limit=self.limit,
            reranker_config=self.reranker_config,
        )
