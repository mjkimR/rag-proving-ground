"""Qdrant BM25 sparse embedding wrapper."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

from rag_core.ai.sparse.interface import SparseEmbeddingModel
from rag_core.ai.sparse.schemas import SparseVector
from rag_core.ai.sparse.utils import coerce_sparse_vector

QDRANT_BM25_MODEL = "Qdrant/bm25"


class QdrantBM25SparseEmbeddings(SparseEmbeddingModel):
    """Thin wrapper around FastEmbed's sparse models."""

    name: ClassVar[str] = "en-bm25"
    requires_server_side_idf: ClassVar[bool] = False

    @classmethod
    def from_config(cls, **kwargs: Any) -> QdrantBM25SparseEmbeddings:
        """Create a QdrantBM25SparseEmbeddings instance from configuration/kwargs."""
        return cls(**kwargs)

    def __init__(
        self,
        *,
        model_name: str = QDRANT_BM25_MODEL,
        batch_size: int = 256,
        cache_dir: str | None = None,
        threads: int | None = None,
        providers: Sequence[Any] | None = None,
        parallel: int | None = None,
        model_kwargs: Mapping[str, Any] | None = None,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than 0.")
        self.model_name = model_name
        self._encoder = self._build_encoder(
            model_name=model_name,
            batch_size=batch_size,
            cache_dir=cache_dir,
            threads=threads,
            providers=providers,
            parallel=parallel,
            model_kwargs=dict(model_kwargs or {}),
        )

    def embed_documents(self, texts: list[str]) -> list[SparseVector]:
        return [coerce_sparse_vector(vector) for vector in self._encoder.embed_documents(texts)]

    def embed_query(self, text: str) -> SparseVector:
        return coerce_sparse_vector(self._encoder.embed_query(text))

    @staticmethod
    def _build_encoder(
        *,
        model_name: str,
        batch_size: int,
        cache_dir: str | None,
        threads: int | None,
        providers: Sequence[Any] | None,
        parallel: int | None,
        model_kwargs: dict[str, Any],
    ) -> Any:
        try:
            from langchain_qdrant import FastEmbedSparse
        except ImportError as exc:
            raise ValueError(
                "The 'langchain_qdrant' and 'fastembed' packages are required for Qdrant BM25 sparse embeddings."
            ) from exc
        return FastEmbedSparse(
            model_name=model_name,
            batch_size=batch_size,
            cache_dir=cache_dir,
            threads=threads,
            providers=providers,
            parallel=parallel,
            **model_kwargs,
        )
