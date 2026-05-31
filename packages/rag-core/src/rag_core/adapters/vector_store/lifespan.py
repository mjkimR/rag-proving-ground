from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

from rag_core.adapters.vector_store.config import get_vector_db_settings
from rag_core.adapters.vector_store.factory import vector_store_cache
from rag_core.adapters.vector_store.instance import close_vector_store, setup_vector_store_provider


@asynccontextmanager
async def lifespan_vector_store(app: FastAPI):
    settings = get_vector_db_settings()
    await setup_vector_store_provider(settings)

    yield

    # Cleanup on shutdown
    await close_vector_store()
    # Clear the vector store cache
    vector_store_cache.clear()
