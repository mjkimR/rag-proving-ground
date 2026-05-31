from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any

from langchain_core.vectorstores import VectorStore


class VectorStoreProvider(ABC):
    def __init__(self, client: Any):
        self.client = client

    @classmethod
    @abstractmethod
    def from_env(cls) -> "VectorStoreProvider":
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the vector store provider."""
        pass

    @abstractmethod
    async def create_vector_store(self, collection_name: str, model_name: str) -> VectorStore:
        """Create and return a VectorStore instance."""
        pass

    @abstractmethod
    async def check_health(self) -> bool:
        """Check connection health of the vector store."""
        pass


@contextmanager
def import_error_handler(kind: str):
    """Context manager to handle import errors for vector store dependencies."""
    try:
        yield
    except ImportError as e:
        raise ImportError(
            f"Failed to import dependencies for vector store kind '{kind}'. Please install the required package."
        ) from e
