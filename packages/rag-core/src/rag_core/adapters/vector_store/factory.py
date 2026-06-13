from cachetools import LRUCache
from langchain_core.vectorstores import VectorStore

from rag_core.adapters.vector_store.config import get_vector_db_settings
from rag_core.adapters.vector_store.interface import VectorStoreProvider

vector_store_cache = LRUCache(maxsize=16)


class VectorStoreFactory:
    """Factory for creating and caching LangChain VectorStore instances based on provider settings."""

    def __init__(self, provider: VectorStoreProvider):
        """Initializes the VectorStoreFactory.

        Args:
            provider: The vector store provider to delegate instance creation to.
        """
        self.provider = provider

    async def get_vector_store(
        self,
        collection_name: str,
        model_name: str,
        *,
        distance: str = "cosine",
        retrieval_mode: str = "dense",
        sparse_model: str | None = None,
    ) -> VectorStore:
        """Returns a cached or newly created VectorStore instance suitable for the provider type.

        Args:
            collection_name: The name of the collection in the vector database.
            model_name: The name of the dense embedding model.
            distance: The distance metric to use (e.g., "cosine", "euclidean"). Defaults to "cosine".
            retrieval_mode: The retrieval mode, either "dense", "sparse", or "hybrid". Defaults to "dense".
            sparse_model: The name of the sparse embedding model, if hybrid/sparse. Defaults to None.

        Returns:
            VectorStore: An initialized LangChain VectorStore instance.
        """
        settings = get_vector_db_settings()

        cache_key = (settings.provider, collection_name, model_name, distance, retrieval_mode, sparse_model)
        if cache_key in vector_store_cache:
            return vector_store_cache[cache_key]

        store = await self.provider.create_vector_store(
            collection_name,
            model_name,
            distance=distance,
            retrieval_mode=retrieval_mode,
            sparse_model=sparse_model,
        )
        vector_store_cache[cache_key] = store
        return store
