import langchain_core.vectorstores
from loguru import logger

from rag_core.adapters.vector_store.config import VectorDBProviderType, VectorDBSettings
from rag_core.adapters.vector_store.factory import VectorStoreFactory
from rag_core.adapters.vector_store.interface import VectorStoreProvider
from rag_core.adapters.vector_store.registry import VectorStoreRegistry

_vector_store_provider: VectorStoreProvider | None = None


def set_vector_store_provider(provider: VectorStoreProvider) -> None:
    """Set the global vector store provider instance."""
    global _vector_store_provider
    if _vector_store_provider is not None:
        raise RuntimeError("Vector Store provider is already initialized.")
    _vector_store_provider = provider


def get_vector_store_provider() -> VectorStoreProvider:
    """Get the global vector store provider instance."""
    global _vector_store_provider
    if _vector_store_provider is None:
        raise RuntimeError("Vector Store provider is not initialized. Check lifespan.")
    return _vector_store_provider


def get_vector_store_factory() -> VectorStoreFactory:
    """Get the global vector store factory instance."""
    return VectorStoreFactory(get_vector_store_provider())


async def get_vector_store(collection_name: str, model_name: str) -> langchain_core.vectorstores.VectorStore:
    """Get a LangChain VectorStore instance."""
    factory = get_vector_store_factory()
    return await factory.get_vector_store(collection_name, model_name)


async def setup_vector_store_provider(settings: VectorDBSettings) -> None:
    """Setup the global vector store provider instance."""
    global _vector_store_provider
    if _vector_store_provider is not None:
        logger.info("Vector Store provider is already initialized.")
        return  # Already initialized

    if settings.provider == VectorDBProviderType.NONE:
        logger.info("Vector Store provider is set to 'none'. Skipping initialization.")
        return

    logger.info(f"Initializing vector store provider of provider: {settings.provider}")
    provider_cls = VectorStoreRegistry.get_provider_cls(settings.provider)
    provider = provider_cls.from_env()
    _vector_store_provider = provider
    logger.info("Vector Store provider initialized successfully.")


async def close_vector_store() -> None:
    """Close the global vector store provider instance."""
    global _vector_store_provider
    provider = _vector_store_provider
    _vector_store_provider = None
    if provider:
        provider.close()
        logger.info("Global vector store provider closed.")
