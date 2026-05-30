from typing import Any

from app_file_storage import get_storage_client
from app_file_storage.config import get_file_storage_settings
from app_file_storage.instance import setup_storage_client
from loguru import logger

from rag_core.adapters.parser.cache import ParserCache
from rag_core.adapters.parser.factory import ParserFactory
from rag_core.adapters.parser.interface import Parser, ParserInput
from rag_core.adapters.parser.registry import ParserRegistry
from rag_core.config import get_parser_settings


async def _get_cache() -> ParserCache:
    """Return a ParserCache backed by the global FileStorageClient.

    If the client has not been initialized (e.g. running outside a FastAPI
    lifespan), a warning is logged and the client is auto-configured from
    environment variables so that experiments work without manual setup.
    """
    try:
        client = get_storage_client()
    except RuntimeError:
        logger.warning(
            "FileStorageClient is not initialized. "
            "Auto-configuring from environment variables (FS_PROVIDER, etc.). "
            "For production use, initialize via `app_file_storage.lifespan_file_storage`."
        )
        await setup_storage_client(get_file_storage_settings())
        client = get_storage_client()
    return ParserCache(client)


def register_parser(parser_class: type[Parser]) -> None:
    """Register a parser provider."""
    ParserRegistry.register(parser_class)


def get_parser(provider: str | None = None) -> Parser:
    """Get the configured parser engine."""
    provider = provider or get_parser_settings().provider
    return ParserFactory.create_parser(provider=provider)


async def parse_document(
    parser_input: ParserInput,
    *,
    provider: str | None = None,
) -> Any:
    """Parse a document with the configured parser engine."""
    parser = get_parser(provider=provider)

    if parser_input.content is None:
        return await parser.parse(parser_input)

    cache = await _get_cache()

    md5_hash = await cache.store_file(parser_input)
    cached_data = await cache.get_result(md5_hash, parser.name, schema_version=parser.schema_version)
    if cached_data is not None:
        return parser.from_cache_data(cached_data)

    result = await parser.parse(parser_input)
    await cache.store_result(
        md5_hash,
        parser.name,
        parser.to_cache_data(result),
        schema_version=parser.schema_version,
    )
    return result


async def parse_file(
    content: bytes,
    *,
    filename: str,
    content_type: str | None = None,
    metadata: dict[str, Any] | None = None,
    provider: str | None = None,
) -> Any:
    """Parse file bytes with the configured parser engine."""
    return await parse_document(
        ParserInput(
            content=content,
            filename=filename,
            content_type=content_type,
            metadata=metadata or {},
        ),
        provider=provider,
    )


async def parse_upload_file(
    upload_file: Any,
    *,
    metadata: dict[str, Any] | None = None,
    provider: str | None = None,
) -> Any:
    """Parse a FastAPI/Starlette UploadFile with the configured parser engine."""
    return await parse_document(
        await ParserInput.from_upload_file(upload_file, metadata=metadata),
        provider=provider,
    )


async def parse_source(
    source: str,
    *,
    metadata: dict[str, Any] | None = None,
    provider: str | None = None,
) -> Any:
    """Parse a URI or local source reference with the configured parser engine."""
    return await parse_document(
        ParserInput(source=source, metadata=metadata or {}),
        provider=provider,
    )
