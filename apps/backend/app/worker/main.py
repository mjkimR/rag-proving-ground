"""FastStream worker application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

# Load .env (same pattern as main.py)
try:
    from dotenv import load_dotenv

    env_in_cwd = Path(".env")
    env_in_workspace = Path(__file__).resolve().parents[3] / ".env"
    if env_in_cwd.exists():
        load_dotenv(dotenv_path=env_in_cwd)
    elif env_in_workspace.exists():
        load_dotenv(dotenv_path=env_in_workspace)
    else:
        load_dotenv()
except ImportError:
    pass


from typing import cast

from app.worker.broker import broker
from app.worker.handlers.ingest import router as ingest_router
from app.worker.handlers.reprocess import router as reprocess_router
from app.worker.recovery import recover_stuck_documents
from app_file_storage import lifespan_file_storage
from app_http_client import lifespan_http_client
from fastapi import FastAPI
from faststream import FastStream
from loguru import logger
from rag_core.adapters.vector_store import lifespan_vector_store


class StateDummy:
    pass


class AppWrapper:
    """Wrapper that provides a .state attribute to satisfy FastAPI lifespan context managers."""

    def __init__(self):
        self.state = StateDummy()


wrapper = AppWrapper()


@asynccontextmanager
async def lifespan():
    """Worker lifespan: initialize shared resources and run recovery."""
    logger.info("Worker starting up...")

    async with (
        lifespan_http_client(cast(FastAPI, wrapper)),
        lifespan_file_storage(cast(FastAPI, wrapper)),
        lifespan_vector_store(cast(FastAPI, wrapper)),
    ):
        # Recovery: stuck documents in QUEUED status
        await recover_stuck_documents(broker)
        yield

    logger.info("Worker shutting down...")


broker.include_router(ingest_router)
broker.include_router(reprocess_router)

app = FastStream(broker, lifespan=lifespan)
