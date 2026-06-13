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


# Global registry for active and default parsers populated from database
_ACTIVE_PARSERS: dict[str, dict[str, Any]] = {}
_DEFAULT_PARSER: dict[str, Any] | None = None


def update_parser_registry(parsers: list[dict[str, Any]]) -> None:
    """Updates the in-memory active and default parser configurations in the registry.

    Args:
        parsers: A list of parser configurations, typically loaded from the database.
    """
    global _ACTIVE_PARSERS, _DEFAULT_PARSER
    _ACTIVE_PARSERS = {p["name"]: p for p in parsers if p.get("is_active", True)}
    _DEFAULT_PARSER = None
    for p in parsers:
        if p.get("is_active", True) and p.get("is_default", False):
            _DEFAULT_PARSER = p
            break


def register_parser(parser_class: type[Parser]) -> None:
    """Registers a parser provider class in the global ParserRegistry.

    Args:
        parser_class: The parser class implementing the `Parser` interface.
    """
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
    """Retrieves the configured document parser engine.

    If no provider is specified, falls back to the default active parser from the
    registry or application settings.

    Args:
        provider: Optional provider name (e.g., "docling", "native_text").

    Returns:
        Parser: An initialized parser engine.
    """
    resolved_provider = provider
    if not resolved_provider:
        resolved_provider = _DEFAULT_PARSER["name"] if _DEFAULT_PARSER else get_parser_settings().provider

    parser = ParserFactory.create_parser(provider=resolved_provider)

    # Override configuration attributes dynamically if registered in DB config
    cached_parser = _ACTIVE_PARSERS.get(resolved_provider)
    if cached_parser and cached_parser.get("connection_info"):
        conn_info = cached_parser["connection_info"]
        if resolved_provider == "docling":
            if hasattr(parser, "base_url") and "base_url" in conn_info:
                parser.base_url = conn_info["base_url"].rstrip("/")  # type: ignore
            if hasattr(parser, "timeout") and "timeout" in conn_info:
                parser.timeout = float(conn_info["timeout"])  # type: ignore
        elif resolved_provider == "native_text":
            if hasattr(parser, "max_page_chars") and "max_page_chars" in conn_info:
                parser.max_page_chars = int(conn_info["max_page_chars"])  # type: ignore

    return parser


def _ensure_elements(doc: Any) -> Any:
    """Ensure a ParsedDocument has elements if they are missing but text exists."""
    if not hasattr(doc, "elements") or doc.elements:
        return doc

    from rag_core.adapters.parser.providers import NativeTextParser

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
    """Parses a document using the specified parser engine, optionally utilizing caching.

    If the document matches text format (e.g., Markdown, plain text), it defaults
    to using the "native_text" provider if no provider is explicitly requested.

    Args:
        parser_input: The input document configuration containing the source, bytes, or file info.
        provider: Optional name of the parser provider to use.
        ignore_cache: If True, bypasses cache checks and forces fresh parsing. Defaults to False.
        parsing_config_hash: Optional hash identifying the parsing settings to scope cache lookups.

    Returns:
        Any: The parsed result object (typically a ParsedDocument).
    """
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
    """Parses a file from its raw bytes using the configured parser engine.

    Args:
        content: The raw binary bytes of the file.
        filename: The name of the file.
        content_type: Optional MIME type of the file.
        metadata: Optional dictionary of additional metadata.
        provider: Optional name of the parser provider to use.
        ignore_cache: If True, bypasses cache checks and forces fresh parsing. Defaults to False.
        parsing_config_hash: Optional hash identifying the parsing settings to scope cache.

    Returns:
        Any: The parsed result object.
    """
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
    """Parses an uploaded file (e.g., FastAPI UploadFile) using the configured parser engine.

    Args:
        upload_file: The FastAPI/Starlette upload file object.
        metadata: Optional dictionary of additional metadata.
        provider: Optional name of the parser provider to use.
        parsing_config_hash: Optional hash identifying the parsing settings to scope cache.

    Returns:
        Any: The parsed result object.
    """
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
    """Parses a document from a URI or local path reference using the configured parser engine.

    Args:
        source: The URI or local path to the document.
        metadata: Optional dictionary of additional metadata.
        provider: Optional name of the parser provider to use.
        parsing_config_hash: Optional hash identifying the parsing settings to scope cache.

    Returns:
        Any: The parsed result object.
    """
    return await parse_document(
        ParserInput(source=source, metadata=metadata or {}),
        provider=provider,
        parsing_config_hash=parsing_config_hash,
    )
