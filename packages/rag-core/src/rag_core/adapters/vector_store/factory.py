import hashlib
import json

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
        Uses a hashed collection name based on the vector index configurations to share collections,
        facilitating multi-tenancy.
        """
        settings = get_vector_db_settings()

        # Calculate a unique physical collection name by hashing the physical vector specifications
        spec = {
            "model_name": model_name,
            "distance": "cosine",
        }
        serialized = json.dumps(spec, sort_keys=True)
        spec_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
        physical_collection_name = f"vector_store_{spec_hash}"

        cache_key = (settings.provider, collection_name, model_name)
        if cache_key in vector_store_cache:
            return vector_store_cache[cache_key]

        store = await self.provider.create_vector_store(physical_collection_name, model_name)
        vector_store_cache[cache_key] = store
        return store
