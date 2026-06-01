from contextlib import asynccontextmanager
from pathlib import Path

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

from app.router import router
from app.worker.broker import broker
from app_file_storage import lifespan_file_storage
from app_http_client import lifespan_http_client
from app_layer_base.base.exceptions.handler import set_exception_handler
from app_layer_base.core import middlewares
from app_layer_base.core.log import logger
from fastapi import FastAPI
from rag_core.adapters.vector_store import lifespan_vector_store
from starlette.responses import RedirectResponse


def get_lifespan():
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting app lifespan")
        async with lifespan_http_client(app), lifespan_file_storage(app), lifespan_vector_store(app):
            await broker.connect()
            yield
            await broker.close()
        logger.info("End of app lifespan")

    return lifespan


def create_app():
    """Create the FastAPI app and include the router."""
    lifespan = get_lifespan()
    app = FastAPI(
        title="ExampleApp",
        version="0.0.1",
        lifespan=lifespan,
        swagger_ui_parameters={
            "persistAuthorization": True,
            "docExpansion": "none",
            "filter": True,
        },
    )

    @app.get("/")
    async def root():
        return RedirectResponse(url="/docs")

    # Others
    middlewares.timeout_middleware.add_middleware(app)
    middlewares.query_counter.add_middleware(app)

    # Security middleware
    middlewares.security_header.add_middleware(app)
    middlewares.cors_middleware.add_middleware(app)

    # Request ID middleware (Last one to ensure all logs have request ID)
    middlewares.request_id_middleware.add_middleware(app)

    app.include_router(router)

    set_exception_handler(app)
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(create_app(), host="localhost", port=8389)
