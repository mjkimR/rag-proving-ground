from cachetools import LRUCache
from langchain_core.vectorstores import VectorStore

from rag_core.adapters.vector_store.config import get_vector_db_settings
from rag_core.adapters.vector_store.interface import VectorStoreProvider

vector_store_cache = LRUCache(maxsize=16)


class VectorStoreFactory:
    def __init__(self, provider: VectorStoreProvider):
        self.provider = provider

    async def get_vector_store(self, collection_name: str, model_name: str) -> VectorStore:
        """
        Returns a VectorStore implementation suitable for the client type.

        TODO: More detailed configuration (index settings, etc.) / multi vector search / ...
        """
        settings = get_vector_db_settings()
        cache_key = (settings.provider, collection_name, model_name)
        if cache_key in vector_store_cache:
            return vector_store_cache[cache_key]
        store = await self.provider.create_vector_store(collection_name, model_name)
        vector_store_cache[cache_key] = store
        return store
