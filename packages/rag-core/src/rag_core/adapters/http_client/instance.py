from threading import RLock

import httpx
from loguru import logger

from rag_core.config import get_http_client_settings

_http_client: httpx.AsyncClient | None = None
_http_sync_client: httpx.Client | None = None
_http_client_lock = RLock()
_http_sync_client_lock = RLock()


def _create_http_client() -> httpx.AsyncClient:
    settings = get_http_client_settings()
    return httpx.AsyncClient(
        timeout=httpx.Timeout(settings.timeout),
        limits=httpx.Limits(
            max_connections=settings.max_connections,
            max_keepalive_connections=settings.max_keepalive_connections,
            keepalive_expiry=settings.keepalive_expiry,
        ),
    )


def _create_http_sync_client() -> httpx.Client:
    settings = get_http_client_settings()
    return httpx.Client(
        timeout=httpx.Timeout(settings.timeout),
        limits=httpx.Limits(
            max_connections=settings.max_connections,
            max_keepalive_connections=settings.max_keepalive_connections,
            keepalive_expiry=settings.keepalive_expiry,
        ),
    )


def set_http_client(client: httpx.AsyncClient) -> None:
    """Set the global HTTP client instance."""
    global _http_client
    with _http_client_lock:
        if _http_client is not None:
            raise RuntimeError("HTTP client is already initialized.")
        _http_client = client


def set_http_sync_client(client: httpx.Client) -> None:
    """Set the global synchronous HTTP client instance."""
    global _http_sync_client
    with _http_sync_client_lock:
        if _http_sync_client is not None:
            raise RuntimeError("Synchronous HTTP client is already initialized.")
        _http_sync_client = client


def get_http_client() -> httpx.AsyncClient:
    """Get the global HTTP client instance."""
    global _http_client
    if _http_client is None:
        with _http_client_lock:
            if _http_client is None:
                logger.info("Lazy initializing global httpx AsyncClient")
                _http_client = _create_http_client()
                logger.info("HTTP client initialized successfully.")
    return _http_client


def get_http_sync_client() -> httpx.Client:
    """Get the global synchronous HTTP client instance."""
    global _http_sync_client
    if _http_sync_client is None:
        with _http_sync_client_lock:
            if _http_sync_client is None:
                logger.info("Lazy initializing global httpx Client (Sync)")
                _http_sync_client = _create_http_sync_client()
                logger.info("Synchronous HTTP client initialized successfully.")
    return _http_sync_client


async def setup_http_client() -> None:
    """Setup the global HTTP client instance."""
    if _http_client is not None:
        logger.info("HTTP client is already initialized.")
        return

    logger.info("Initializing global httpx AsyncClient")
    get_http_client()
    logger.info("HTTP client initialized successfully.")


def setup_http_sync_client() -> None:
    """Setup the global synchronous HTTP client instance."""
    if _http_sync_client is not None:
        logger.info("Synchronous HTTP client is already initialized.")
        return

    logger.info("Initializing global httpx Client (Sync)")
    get_http_sync_client()
    logger.info("Synchronous HTTP client initialized successfully.")


async def close_http_client() -> None:
    """Close the global HTTP client instance."""
    global _http_client
    with _http_client_lock:
        client = _http_client
        _http_client = None
    if client:
        await client.aclose()
        logger.info("Global httpx AsyncClient closed.")


def close_http_sync_client() -> None:
    """Close the global synchronous HTTP client instance."""
    global _http_sync_client
    with _http_sync_client_lock:
        client = _http_sync_client
        _http_sync_client = None
    if client:
        client.close()
        logger.info("Global httpx Client (Sync) closed.")
