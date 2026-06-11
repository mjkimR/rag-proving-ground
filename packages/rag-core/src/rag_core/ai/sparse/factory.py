"""Factory for resolving sparse embedding instances."""

from __future__ import annotations

from typing import Any

from rag_core.ai.sparse.interface import SparseEmbeddingModel
from rag_core.ai.sparse.providers import register_default_sparse_models
from rag_core.ai.sparse.registry import SparseEmbeddingRegistry


class SparseEmbeddingFactory:
    """Factory facade for sparse embedding model creation."""

    @classmethod
    def create_embeddings(cls, model_name: str | None = None, **kwargs: Any) -> SparseEmbeddingModel:
        """Create a sparse embedding model instance by name."""
        register_default_sparse_models()
        name = model_name or "en-bm25"

        model_class = SparseEmbeddingRegistry.get_model_class(name)
        return model_class.from_config(**kwargs)

    @classmethod
    def list_supported_models(cls) -> list[str]:
        """List all supported sparse embedding models for configuration."""
        from rag_core.embeddings.schemas import SparseEmbeddingModel as ModelEnum

        return [model.value for model in ModelEnum]
