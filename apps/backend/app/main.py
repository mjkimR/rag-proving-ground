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


async def init_db_and_seed_models_parsers() -> None:
    """Seed models and parsers on startup if tables are empty, and load cache registries."""
    from app.features.providers.ai_models.models import AIModel
    from app.features.providers.document_parsers.models import DocumentParser
    from app.features.providers.routes.cache import refresh_ai_models_cache, refresh_document_parsers_cache
    from app_layer_base.core.database.transaction import AsyncTransaction
    from rag_core.adapters.parser.registry import ParserRegistry
    from rag_core.ai.models import _fetch_raw_model_info_from_gateway, get_litellm_settings
    from rag_core.config import get_parser_settings
    from sqlalchemy import select

    async with AsyncTransaction() as session:
        # 1. AI Models Seeding
        models_stmt = select(AIModel)
        models_res = await session.execute(models_stmt)
        if not models_res.scalars().all():
            logger.info("AI Models table is empty. Seeding from LiteLLM gateway...")
            settings = get_litellm_settings()
            try:
                model_list = _fetch_raw_model_info_from_gateway()
            except Exception as e:
                logger.warning(f"Could not connect to LiteLLM gateway during startup seeding: {e}. Using placeholders.")
                model_list = [
                    {"model_name": settings.default_llm_model, "metadata": {"role": "llm"}},
                    {"model_name": settings.default_embedding_model, "metadata": {"role": "embedding"}},
                    {"model_name": settings.default_reranker_model, "metadata": {"role": "reranker"}},
                ]

            for entry in model_list:
                name = entry.get("model_name")
                if not name:
                    continue

                metadata = entry.get("metadata") or {}
                role = metadata.get("role") or metadata.get("type")
                if not role and "tags" in metadata:
                    tags = metadata.get("tags") or []
                    if "embedding" in tags:
                        role = "embedding"
                    elif "reranker" in tags:
                        role = "reranker"
                    elif "llm" in tags or "chat" in tags:
                        role = "llm"
                if not role:
                    name_lower = name.lower()
                    if "embedding" in name_lower or ("bge" in name_lower and "rerank" not in name_lower):
                        role = "embedding"
                    elif "reranker" in name_lower or "rerank" in name_lower:
                        role = "reranker"
                    else:
                        role = "llm"

                # Check default status
                is_default = (
                    (role == "llm" and name == settings.default_llm_model)
                    or (role == "embedding" and name == settings.default_embedding_model)
                    or (role == "reranker" and name == settings.default_reranker_model)
                )

                litellm_params = entry.get("litellm_params") or {}
                raw_model_val = litellm_params.get("model") or ""
                provider = "custom"
                if "/" in raw_model_val:
                    provider = raw_model_val.split("/")[0]
                elif "/" in name:
                    provider = name.split("/")[0]

                connection_info = {}

                session.add(
                    AIModel(
                        name=name,
                        provider=provider,
                        model_type=role,
                        is_active=True,
                        is_default=is_default,
                        connection_info=connection_info,
                        extra_metadata={"model_params": metadata.get("model_params") or {}},
                    )
                )

        # 2. Document Parsers Seeding
        parsers_stmt = select(DocumentParser)
        parsers_res = await session.execute(parsers_stmt)
        if not parsers_res.scalars().all():
            logger.info("Document Parsers table is empty. Seeding from ParserRegistry...")
            parser_settings = get_parser_settings()
            parsers_list = ParserRegistry.list_parsers()

            for name in parsers_list:
                is_default = name == parser_settings.provider
                session.add(
                    DocumentParser(
                        name=name,
                        is_active=True,
                        is_default=is_default,
                        connection_info={},
                        extra_metadata={},
                    )
                )

        await session.flush()

        # 3. Reload cache registries
        await refresh_ai_models_cache(session)
        await refresh_document_parsers_cache(session)


def get_lifespan():
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting app lifespan")
        async with lifespan_http_client(app), lifespan_file_storage(app), lifespan_vector_store(app):
            # Register synonym loader callback
            from app.features.knowledge.synonyms.repos import SynonymMapRepository
            from app_layer_base.base.repos.query_options import ListQueryOptions
            from app_layer_base.core.database.transaction import AsyncTransaction
            from rag_core.query_rewrite.synonym_expander import register_synonym_loader

            async def db_synonym_loader() -> dict[str, list[str]]:
                synonyms: dict[str, list[str]] = {}
                repo = SynonymMapRepository()

                async with AsyncTransaction() as session:
                    query_options = ListQueryOptions(limit=None)
                    res = await repo.get_multi(session, query_options=query_options)
                    for item in res.items:
                        synonyms[item.keyword] = item.synonyms

                logger.debug(f"Loaded {len(synonyms)} synonym mappings from database.")
                return synonyms

            register_synonym_loader(db_synonym_loader)

            # Seed and populate registry caches on boot
            from rag_core.adapters.prompt.providers import register_default_prompt_providers

            register_default_prompt_providers()
            await init_db_and_seed_models_parsers()
            await broker.startup()
            yield
            await broker.shutdown()
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
