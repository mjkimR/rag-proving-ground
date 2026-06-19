"""Taskiq worker application entry point."""

from contextlib import AsyncExitStack
from pathlib import Path
from typing import cast

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


# Import tasks to ensure they are registered on the broker
import app.worker.handlers.ingest  # noqa: F401
from app.worker.broker import broker
from app.worker.recovery import recover_stuck_documents
from app.worker.scheduling import start_dispatchers, stop_dispatchers
from app_file_storage import lifespan_file_storage
from app_http_client import lifespan_http_client
from fastapi import FastAPI
from loguru import logger
from rag_core.adapters.vector_store import lifespan_vector_store
from taskiq import TaskiqEvents, TaskiqState


class StateDummy:
    pass


class AppWrapper:
    """Wrapper that provides a .state attribute to satisfy FastAPI lifespan context managers."""

    def __init__(self):
        self.state = StateDummy()


wrapper = AppWrapper()


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState) -> None:
    """Initialize resources, run recovery, and start DB-polling scheduling dispatchers."""
    logger.info("Worker starting up...")

    stack = AsyncExitStack()
    state.exit_stack = stack

    # Enter client lifespans
    await stack.enter_async_context(lifespan_http_client(cast(FastAPI, wrapper)))
    await stack.enter_async_context(lifespan_file_storage(cast(FastAPI, wrapper)))
    await stack.enter_async_context(lifespan_vector_store(cast(FastAPI, wrapper)))

    # Recovery: stuck documents
    await recover_stuck_documents(broker)

    # Start scheduling dispatchers
    await start_dispatchers(broker)

    logger.info("Worker startup complete.")


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def shutdown(state: TaskiqState) -> None:
    """Gracefully stop scheduling dispatchers and close resources."""
    logger.info("Worker shutting down...")

    # Stop scheduling dispatchers
    await stop_dispatchers()

    # Close client lifespans
    if hasattr(state, "exit_stack"):
        await state.exit_stack.aclose()

    logger.info("Worker shutdown complete.")
