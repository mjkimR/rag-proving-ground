import json
import time
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


def _is_text_format(parser_input: ParserInput) -> bool:
    """Check if the document is a plain text, Markdown, or HTML file."""
    filename = (parser_input.filename or "").lower()
    mimetype = (parser_input.content_type or "").lower()

    return filename.endswith((".txt", ".text", ".md", ".markdown", ".html", ".htm")) or mimetype in (
        "text/plain",
        "text/markdown",
        "text/x-markdown",
        "text/html",
    )


def get_parser(provider: str | None = None) -> Parser:
    """Get the configured parser engine."""
    provider = provider or get_parser_settings().provider
    return ParserFactory.create_parser(provider=provider)


def _ensure_elements(doc: Any) -> Any:
    """Ensure a ParsedDocument has elements if they are missing but text exists."""
    if not hasattr(doc, "elements") or doc.elements:
        return doc

    from rag_core.adapters.parser.providers.native_text import NativeTextParser

    logger.warning(
        "ParsedDocument has no elements; reconstructing elements from markdown/html/text "
        "with NativeTextParser fallback."
    )
    parser = NativeTextParser()
    elements = []

    markdown_val = getattr(doc, "markdown", None)
    html_val = getattr(doc, "html", None)
    text_val = getattr(doc, "text", None)
    doc_id = getattr(doc, "doc_id", "document")

    if markdown_val and markdown_val.strip():
        elements = parser._parse_markdown(markdown_val, doc_id)
    elif html_val and html_val.strip():
        elements = parser._parse_html(html_val, doc_id)
    elif text_val and text_val.strip():
        elements = parser._parse_plain_text(text_val, doc_id)

    if elements:
        for idx, el in enumerate(elements):
            el.order = idx
        pages, elements = parser._assign_synthetic_pages(elements, doc_id)
        doc.elements = elements
        doc.pages = pages

    return doc


async def parse_document(
    parser_input: ParserInput,
    *,
    provider: str | None = None,
    ignore_cache: bool = False,
    parsing_config_hash: str | None = None,
) -> Any:
    """Parse a document with the configured parser engine."""
    if provider is None and _is_text_format(parser_input):
        provider = "native_text"

    parser = get_parser(provider=provider)

    if parsing_config_hash is None:
        from rag_core.parsers import KnowledgeParsingConfig, knowledge_parsing_config_hash

        basic_config = KnowledgeParsingConfig(provider=parser.name)
        parsing_config_hash = knowledge_parsing_config_hash(basic_config)

    if parser_input.content is None:
        start_time = time.perf_counter()
        result = await parser.parse(parser_input)
        duration_sec = time.perf_counter() - start_time
        result = _ensure_elements(result)
        if hasattr(result, "metadata") and isinstance(result.metadata, dict):
            result.metadata["cache_hit"] = False
            result.metadata["parse_duration_sec"] = duration_sec
        return result

    cache = await _get_cache()

    content_hash = await cache.store_file(parser_input, parsing_config_hash)

    if not ignore_cache:
        start_time = time.perf_counter()
        cached_data = await cache.get_result(content_hash, parsing_config_hash)
        if cached_data is not None:
            result = parser.from_cache_data(cached_data)
            duration_sec = time.perf_counter() - start_time

            # Retrieve original duration from meta.json if possible
            original_duration = None
            try:
                meta_key = cache._meta_key(content_hash, parsing_config_hash)
                if await cache._client.file_exists(meta_key):
                    meta_bytes = await cache._client.download_file(meta_key)
                    meta = json.loads(meta_bytes.decode("utf-8"))
                    original_duration = meta.get("parse_durations", {}).get(parser.name)
            except Exception as e:
                logger.warning(f"Failed to load parse duration from cache meta: {e}")

            if hasattr(result, "metadata") and isinstance(result.metadata, dict):
                result.metadata["cache_hit"] = True
                result.metadata["parse_duration_sec"] = (
                    original_duration if original_duration is not None else duration_sec
                )
            return result

    start_time = time.perf_counter()
    result = await parser.parse(parser_input)
    duration_sec = time.perf_counter() - start_time

    result = _ensure_elements(result)

    await cache.store_result(
        content_hash,
        parsing_config_hash,
        parser.to_cache_data(result),
        provider=parser.name,
        parse_duration_sec=duration_sec,
    )

    if hasattr(result, "metadata") and isinstance(result.metadata, dict):
        result.metadata["cache_hit"] = False
        result.metadata["parse_duration_sec"] = duration_sec

    return result


async def parse_file(
    content: bytes,
    *,
    filename: str,
    content_type: str | None = None,
    metadata: dict[str, Any] | None = None,
    provider: str | None = None,
    ignore_cache: bool = False,
    parsing_config_hash: str | None = None,
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
        ignore_cache=ignore_cache,
        parsing_config_hash=parsing_config_hash,
    )


async def parse_upload_file(
    upload_file: Any,
    *,
    metadata: dict[str, Any] | None = None,
    provider: str | None = None,
    parsing_config_hash: str | None = None,
) -> Any:
    """Parse a FastAPI/Starlette UploadFile with the configured parser engine."""
    return await parse_document(
        await ParserInput.from_upload_file(upload_file, metadata=metadata),
        provider=provider,
        parsing_config_hash=parsing_config_hash,
    )


async def parse_source(
    source: str,
    *,
    metadata: dict[str, Any] | None = None,
    provider: str | None = None,
    parsing_config_hash: str | None = None,
) -> Any:
    """Parse a URI or local source reference with the configured parser engine."""
    return await parse_document(
        ParserInput(source=source, metadata=metadata or {}),
        provider=provider,
        parsing_config_hash=parsing_config_hash,
    )
