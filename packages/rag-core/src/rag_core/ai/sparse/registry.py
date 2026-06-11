"""Registry for mapping sparse embedding model identifiers to classes."""

from __future__ import annotations

from typing import ClassVar

from rag_core.ai.sparse.interface import SparseEmbeddingModel


class SparseEmbeddingRegistry:
    """Registry for sparse embedding providers/models."""

    _models: ClassVar[dict[str, type[SparseEmbeddingModel]]] = {}

    @classmethod
    def register(cls, model_class: type[SparseEmbeddingModel]) -> None:
        """Register a sparse embedding model class."""
        model_name = model_class.name
        if model_name in cls._models:
            raise ValueError(f"Sparse embedding model is already registered: {model_name}")
        cls._models[model_name] = model_class

    @classmethod
    def get_model_class(cls, model_name: str) -> type[SparseEmbeddingModel]:
        """Get the registered sparse embedding model class."""
        try:
            return cls._models[model_name]
        except KeyError as exc:
            raise ValueError(f"Unsupported sparse embedding model: {model_name}") from exc

    @classmethod
    def list_models(cls) -> list[str]:
        """List all registered sparse embedding model names."""
        return sorted(cls._models)

    @classmethod
    def clear(cls) -> None:
        """Clear all registered models (mainly for testing)."""
        cls._models.clear()
