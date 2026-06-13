from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any

from langchain_core.vectorstores import VectorStore


class VectorStoreProvider(ABC):
    """Abstract base class defining the interface for vector store providers."""

    def __init__(self, client: Any):
        """Initializes the VectorStoreProvider with the underlying database client.

        Args:
            client: The raw client instance for the target vector database.
        """
        self.client = client

    @classmethod
    @abstractmethod
    def from_env(cls) -> "VectorStoreProvider":
        """Creates a provider instance using configuration from environment variables.

        Returns:
            VectorStoreProvider: An instance of the vector store provider.
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Closes the vector store provider client connection and cleans up resources."""
        pass

    @abstractmethod
    async def create_vector_store(
        self,
        collection_name: str,
        model_name: str,
        *,
        distance: str = "cosine",
        retrieval_mode: str = "dense",
        sparse_model: str | None = None,
    ) -> VectorStore:
        """Creates and returns a LangChain VectorStore instance.

        Args:
            collection_name: The name of the vector database collection.
            model_name: The name of the dense embedding model.
            distance: The distance metric to use (e.g. "cosine", "euclidean"). Defaults to "cosine".
            retrieval_mode: The retrieval strategy, "dense", "sparse", or "hybrid". Defaults to "dense".
            sparse_model: The name of the sparse embedding model, if hybrid/sparse. Defaults to None.

        Returns:
            VectorStore: An initialized LangChain VectorStore instance.
        """
        pass

    @abstractmethod
    async def check_health(self) -> bool:
        """Checks connection health of the vector store backend.

        Returns:
            bool: True if the database is healthy and reachable, False otherwise.
        """
        pass

    @abstractmethod
    async def delete_points(self, collection_name: str, points_selector: Any) -> None:
        """Deletes specific points/documents from a vector store collection.

        Args:
            collection_name: The name of the collection to delete from.
            points_selector: The selector configuration indicating which points to delete.
        """
        pass


@contextmanager
def import_error_handler(kind: str):
    """Context manager to handle import errors for vector store dependencies.

    Args:
        kind: The name or type of the vector store provider (e.g., "qdrant").

    Raises:
        ImportError: If a dependency failed to import, with a user-friendly message.
    """
    try:
        yield
    except ImportError as e:
        raise ImportError(
            f"Failed to import dependencies for vector store kind '{kind}'. Please install the required package."
        ) from e
