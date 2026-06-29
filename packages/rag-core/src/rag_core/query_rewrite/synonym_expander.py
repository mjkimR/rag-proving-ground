import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any, cast
from urllib.parse import unquote, urlparse
from uuid import uuid4

from loguru import logger

from rag_core.config import get_redis_settings, get_synonym_cache_settings

from .word_boundary import (
    WordBoundaryStrategy,
    clear_word_boundary_cache,
    get_word_boundary_strategy,
)

# Global cached synonyms mapping: keyword -> list of synonyms
_CACHED_SYNONYMS: dict[str, list[str]] = {}
_CACHED_VERSION: str | None = None
_VERSION_CHECK_EXPIRES_AT = 0.0
_LOCAL_CACHE_EXPIRES_AT = 0.0
_IS_LOADED = False
_REDIS_CACHE_CLIENT: Any | None = None
_REDIS_CACHE_IMPORT_FAILED = False
_REDIS_CACHE_CONNECT_FAILED = False
_SYNONYMS_VERSION_KEY = "synonyms:version"
_SYNONYMS_LOCAL_REFRESH_LOCK: asyncio.Lock | None = None
_REDIS_READ_FAILED = object()

# Async loader callback registry
_SYNONYM_LOADER_FN: Callable[[], Awaitable[dict[str, list[str]]]] | None = None


def register_synonym_loader(loader_fn: Callable[[], Awaitable[dict[str, list[str]]]]) -> None:
    """Registers the dynamic database/repository loader function for synonyms."""
    global _SYNONYM_LOADER_FN
    _SYNONYM_LOADER_FN = loader_fn
    logger.info("Synonym loader callback registered successfully in rag-core.")


def clear_synonyms_cache() -> None:
    """Invalidates the process-local cache, forcing a reload on the next query."""
    global _IS_LOADED, _CACHED_SYNONYMS, _CACHED_VERSION, _VERSION_CHECK_EXPIRES_AT, _LOCAL_CACHE_EXPIRES_AT
    _IS_LOADED = False
    _CACHED_VERSION = None
    _VERSION_CHECK_EXPIRES_AT = 0.0
    _LOCAL_CACHE_EXPIRES_AT = 0.0
    _CACHED_SYNONYMS.clear()
    clear_word_boundary_cache()
    logger.info("Synonyms in-memory cache cleared in rag-core.")


async def invalidate_synonyms_cache() -> None:
    """Invalidates both process-local and shared synonym caches."""
    clear_synonyms_cache()
    redis_client = _get_redis_cache_client()
    if redis_client is None:
        return

    try:
        await _set_synonyms_version(redis_client, _new_synonyms_version())
        logger.info("Synonyms Redis version bumped in rag-core.")
    except Exception as exc:
        logger.warning(f"Failed to bump synonyms Redis version: {exc}")


async def get_synonyms() -> dict[str, list[str]]:
    """Retrieves the synonyms map, triggering the registered loader if cache is empty."""
    global _IS_LOADED, _CACHED_SYNONYMS
    cache_enabled = get_synonym_cache_settings().enabled
    redis_client = _get_redis_cache_client()
    if redis_client is not None:
        # Redis is only a small invalidation signal. When the local version-check
        # TTL is fresh, avoid Redis entirely and use the worker-local dictionary.
        if _is_local_version_check_fresh():
            return _CACHED_SYNONYMS

        redis_version = await _get_synonyms_version(redis_client)
        if redis_version is _REDIS_READ_FAILED:
            return await _get_synonyms_during_redis_outage()
        version = cast(str | None, redis_version)
        if version is None:
            version = _new_synonyms_version()
            await _set_synonyms_version(redis_client, version)

        if _is_local_cache_current(version):
            _mark_version_checked()
            return _CACHED_SYNONYMS

        # Version mismatch: this worker refreshes its own L1 cache from Postgres.
        # Redis never stores the full synonym dictionary.
        loaded_synonyms, loaded_version = await _refresh_local_synonyms(version=version)
        _store_local_synonyms(loaded_synonyms, version=loaded_version)
        return loaded_synonyms

    if cache_enabled:
        return await _get_synonyms_during_redis_outage()

    # Explicit opt-out path: when SYNONYM_CACHE_ENABLED=false, use the old
    # process-local cache behavior for local/dev environments that do not want Redis.
    if not _IS_LOADED:
        _CACHED_SYNONYMS = await _load_synonyms()
        _IS_LOADED = True
    return _CACHED_SYNONYMS


def _store_local_synonyms(
    synonyms: dict[str, list[str]],
    *,
    version: str | None,
    fallback_ttl: bool = False,
) -> None:
    global _CACHED_SYNONYMS, _CACHED_VERSION, _IS_LOADED, _VERSION_CHECK_EXPIRES_AT, _LOCAL_CACHE_EXPIRES_AT

    _CACHED_SYNONYMS = synonyms
    _CACHED_VERSION = version
    _IS_LOADED = True
    if fallback_ttl:
        _VERSION_CHECK_EXPIRES_AT = 0.0
        _LOCAL_CACHE_EXPIRES_AT = time.monotonic() + get_synonym_cache_settings().local_fallback_ttl_seconds
    else:
        _mark_version_checked()
        _LOCAL_CACHE_EXPIRES_AT = 0.0


def _is_local_cache_current(distributed_version: Any) -> bool:
    return _IS_LOADED and distributed_version is not None and distributed_version == _CACHED_VERSION


def _is_local_version_check_fresh() -> bool:
    return _IS_LOADED and _CACHED_VERSION is not None and time.monotonic() < _VERSION_CHECK_EXPIRES_AT


def _mark_version_checked() -> None:
    global _VERSION_CHECK_EXPIRES_AT
    _VERSION_CHECK_EXPIRES_AT = time.monotonic() + get_synonym_cache_settings().version_check_ttl_seconds


async def _get_synonyms_during_redis_outage() -> dict[str, list[str]]:
    if _IS_LOADED and time.monotonic() < _LOCAL_CACHE_EXPIRES_AT:
        return _CACHED_SYNONYMS

    async with _get_local_refresh_lock():
        if _IS_LOADED and time.monotonic() < _LOCAL_CACHE_EXPIRES_AT:
            return _CACHED_SYNONYMS

        loaded_synonyms = await _load_synonyms()
        _store_local_synonyms(loaded_synonyms, version=None, fallback_ttl=True)
    return loaded_synonyms


async def _load_synonyms() -> dict[str, list[str]]:
    if _SYNONYM_LOADER_FN is None:
        return {}

    try:
        synonyms = await _SYNONYM_LOADER_FN()
        logger.debug(f"Loaded {len(synonyms)} synonym mappings.")
        return synonyms
    except Exception as exc:
        logger.error(f"Failed to load synonyms using registered loader: {exc}")
        return {}


def _get_local_refresh_lock() -> asyncio.Lock:
    global _SYNONYMS_LOCAL_REFRESH_LOCK
    if _SYNONYMS_LOCAL_REFRESH_LOCK is None:
        _SYNONYMS_LOCAL_REFRESH_LOCK = asyncio.Lock()
    return _SYNONYMS_LOCAL_REFRESH_LOCK


def _get_redis_cache_client() -> Any | None:
    global _REDIS_CACHE_CLIENT, _REDIS_CACHE_IMPORT_FAILED, _REDIS_CACHE_CONNECT_FAILED

    cache_settings = get_synonym_cache_settings()
    if not cache_settings.enabled:
        return None
    if _REDIS_CACHE_CLIENT is not None:
        return _REDIS_CACHE_CLIENT
    if _REDIS_CACHE_IMPORT_FAILED or _REDIS_CACHE_CONNECT_FAILED:
        return None

    try:
        from aiocache import Cache
        from aiocache.serializers import StringSerializer
    except ImportError:
        _REDIS_CACHE_IMPORT_FAILED = True
        logger.warning("aiocache[redis] is not available; falling back to process-local synonyms cache.")
        return None

    redis_url = get_redis_settings().url
    parsed = urlparse(redis_url)
    if parsed.scheme not in {"redis", "rediss"}:
        _REDIS_CACHE_CONNECT_FAILED = True
        logger.warning(f"Unsupported Redis URL scheme for synonym cache: {parsed.scheme!r}.")
        return None

    try:
        redis_kwargs: dict[str, Any] = {
            "endpoint": parsed.hostname or "localhost",
            "port": parsed.port or 6379,
            "db": int(parsed.path.lstrip("/") or "0"),
            "namespace": cache_settings.namespace,
            # Redis stores only a lightweight version token, not the synonym map.
            # Keep it as a plain string so version checks are stable across workers.
            "serializer": StringSerializer(),
        }
        if parsed.password is not None:
            redis_kwargs["password"] = unquote(parsed.password)
        if parsed.scheme == "rediss":
            redis_kwargs["ssl"] = True

        cache_factory: Any = Cache
        _REDIS_CACHE_CLIENT = cache_factory(cache_factory.REDIS, **redis_kwargs)
    except Exception as exc:
        _REDIS_CACHE_CONNECT_FAILED = True
        logger.warning(f"Failed to configure Redis synonym cache: {exc}")
        return None

    return _REDIS_CACHE_CLIENT


async def _get_synonyms_version(redis_client: Any) -> str | None | object:
    try:
        version = await redis_client.get(_SYNONYMS_VERSION_KEY)
    except Exception as exc:
        logger.warning(f"Failed to read synonyms Redis version: {exc}")
        return _REDIS_READ_FAILED

    if version is None:
        return None
    if not isinstance(version, str):
        logger.warning("Ignoring malformed synonyms cache version payload.")
        return None
    return version


async def _refresh_local_synonyms(*, version: str) -> tuple[dict[str, list[str]], str]:
    async with _get_local_refresh_lock():
        if _is_local_cache_current(version):
            _mark_version_checked()
            return _CACHED_SYNONYMS, version

        loaded_synonyms = await _load_synonyms()
        return loaded_synonyms, version


async def _set_synonyms_version(redis_client: Any, version: str) -> None:
    try:
        await redis_client.set(_SYNONYMS_VERSION_KEY, version)
        logger.debug("Stored synonym cache version in Redis.")
    except Exception as exc:
        logger.warning(f"Failed to write synonyms Redis version: {exc}")


def _new_synonyms_version() -> str:
    return str(uuid4())


class SynonymExpander:
    """Applies dictionary-based synonym expansions to search queries using a Language Strategy."""

    def __init__(
        self,
        language: str = "en",
        boundary_strategy: WordBoundaryStrategy | None = None,
    ) -> None:
        self.language = language
        self.boundary_strategy = boundary_strategy or get_word_boundary_strategy(language)

    async def expand_query(self, query: str, language: str | None = None) -> str:
        """Appends synonyms in parentheses for matching keywords.

        Uses the boundary strategy (by default the one associated with the configured language)
        to match keywords as whole words.
        """
        synonyms_dict = await get_synonyms()
        if not synonyms_dict:
            return query

        strategy = get_word_boundary_strategy(language) if language is not None else self.boundary_strategy

        expanded_query = query
        for keyword, synonyms in synonyms_dict.items():
            if not keyword or not synonyms:
                continue

            pattern = strategy.get_pattern(keyword)
            if pattern.search(expanded_query):
                synonym_str = ", ".join(synonyms)
                replacement = f"{keyword} ({synonym_str})"
                expanded_query = pattern.sub(replacement, expanded_query)
                logger.debug(
                    f"Expanded keyword '{keyword}' -> '{replacement}' in query using {strategy.__class__.__name__}."
                )

        return expanded_query
