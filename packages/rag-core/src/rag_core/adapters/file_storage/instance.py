from loguru import logger

from rag_core.adapters.file_storage.config import FileStorageSettings
from rag_core.adapters.file_storage.factory import FileStorageFactory
from rag_core.adapters.file_storage.interface import FileStorageClient

_file_storage_client: FileStorageClient | None = None


def set_file_storage_client(client: FileStorageClient) -> None:
    """Set the global file storage client instance."""
    global _file_storage_client
    if _file_storage_client is not None:
        raise RuntimeError("File storage client is already initialized.")
    _file_storage_client = client


def get_storage_client() -> FileStorageClient:
    """Get the global file storage client instance."""
    if _file_storage_client is None:
        raise RuntimeError("File storage client is not initialized. Check lifespan.")
    return _file_storage_client


async def setup_storage_client(settings: FileStorageSettings) -> None:
    """Setup the global file storage client instance."""
    if _file_storage_client is not None:
        logger.info("File storage client is already initialized.")
        return  # Already initialized
    logger.info(f"Initializing file storage client of provider: {settings.provider}")
    client = await FileStorageFactory.create_client(config=settings)
    set_file_storage_client(client)
    logger.info("File storage client initialized successfully.")


async def close_storage_client() -> None:
    """Close the global file storage client instance."""
    global _file_storage_client
    if _file_storage_client:
        await _file_storage_client.close()
        _file_storage_client = None
