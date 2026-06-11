from abc import ABC, abstractmethod
from typing import ClassVar

from rag_core.ai.sparse.schemas import SparseEmbeddings


class SparseEmbeddingModel(SparseEmbeddings, ABC):
    """Abstract interface for sparse embedding model providers."""

    name: ClassVar[str]
    requires_server_side_idf: ClassVar[bool] = False

    @classmethod
    @abstractmethod
    def from_config(cls, **kwargs) -> "SparseEmbeddingModel":
        """Create a sparse embedding model instance from config and kwargs."""
        pass
