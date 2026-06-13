import langchain_core.vectorstores
from loguru import logger

from rag_core.adapters.vector_store.config import VectorDBProviderType, VectorDBSettings
from rag_core.adapters.vector_store.factory import VectorStoreFactory
from rag_core.adapters.vector_store.interface import VectorStoreProvider
from rag_core.adapters.vector_store.registry import VectorStoreRegistry

_vector_store_provider: VectorStoreProvider | None = None


def set_vector_store_provider(provider: VectorStoreProvider) -> None:
    """Sets the global vector store provider instance.

    Args:
        provider: The vector store provider to set globally.

    Raises:
        RuntimeError: If the global vector store provider has already been set.
    """
    global _vector_store_provider
    if _vector_store_provider is not None:
        raise RuntimeError("Vector Store provider is already initialized.")
    _vector_store_provider = provider


def get_vector_store_provider() -> VectorStoreProvider:
    """Retrieves the global vector store provider instance.

    Returns:
        VectorStoreProvider: The active global vector store provider.

    Raises:
        RuntimeError: If the global vector store provider has not been initialized.
    """
    global _vector_store_provider
    if _vector_store_provider is None:
        raise RuntimeError("Vector Store provider is not initialized. Check lifespan.")
    return _vector_store_provider


def get_vector_store_factory() -> VectorStoreFactory:
    """Retrieves a new factory instance using the global vector store provider.

    Returns:
        VectorStoreFactory: A factory configured with the current global provider.
    """
    return VectorStoreFactory(get_vector_store_provider())


async def get_vector_store(
    collection_name: str,
    model_name: str,
    *,
    distance: str = "cosine",
    retrieval_mode: str = "dense",
    sparse_model: str | None = None,
) -> langchain_core.vectorstores.VectorStore:
    """Retrieves a LangChain VectorStore instance for the specified collection and settings.

    Args:
        collection_name: The name of the vector database collection.
        model_name: The name of the embedding model to associate with the store.
        distance: The distance metric to use (e.g., "cosine", "euclidean"). Defaults to "cosine".
        retrieval_mode: The retrieval mode, either "dense", "sparse", or "hybrid". Defaults to "dense".
        sparse_model: The name of the sparse embedding model, if applicable. Defaults to None.

    Returns:
        langchain_core.vectorstores.VectorStore: The initialized LangChain VectorStore instance.
    """
    factory = get_vector_store_factory()
    return await factory.get_vector_store(
        collection_name,
        model_name,
        distance=distance,
        retrieval_mode=retrieval_mode,
        sparse_model=sparse_model,
    )


async def setup_vector_store_provider(settings: VectorDBSettings) -> None:
    """Sets up the global vector store provider instance based on settings.

    If the provider is already initialized or set to 'none', this function
    will skip initialization.

    Args:
        settings: The configurations containing vector database settings.
    """
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
    """Closes and resets the global vector store provider instance, releasing resources."""
    global _vector_store_provider
    provider = _vector_store_provider
    _vector_store_provider = None
    if provider:
        await provider.close()
        logger.info("Global vector store provider closed.")


async def check_vector_store_health() -> bool:
    """Checks the connection health of the global vector store provider.

    Returns:
        bool: True if the provider is initialized and healthy, False otherwise.
    """
    global _vector_store_provider
    if _vector_store_provider is None:
        return False
    try:
        return await _vector_store_provider.check_health()
    except Exception as exc:
        logger.warning(f"Vector store health check failed: {exc}")
        return False
