from contextlib import asynccontextmanager
from typing import Any

from rag_core.adapters.file_storage.config import get_file_storage_settings
from rag_core.adapters.file_storage.instance import close_storage_client, setup_storage_client


@asynccontextmanager
async def lifespan_file_storage(app: Any):
    """Lifespan context manager to initialize and cleanup the file storage client."""
    settings = get_file_storage_settings()
    await setup_storage_client(settings)

    yield

    # Cleanup on shutdown
    await close_storage_client()
