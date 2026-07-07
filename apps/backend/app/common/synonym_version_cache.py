"""Builds the Redis-backed synonym version cache injected into rag-core.

rag-core keeps synonym expansion stateless (ADR-0008); the backend owns the Redis
connection and registers the client via `register_synonym_version_cache` at startup.
"""

from typing import Any
from urllib.parse import unquote, urlparse

from app_layer_base.core.log import logger
from rag_core.config import get_redis_settings, get_synonym_cache_settings


def build_synonym_version_cache() -> Any | None:
    """Creates an aiocache Redis client storing only the synonym version token.

    Returns None (process-local TTL caching) when the cache is disabled or the
    Redis client cannot be configured.
    """
    cache_settings = get_synonym_cache_settings()
    if not cache_settings.enabled:
        return None

    try:
        from aiocache import Cache
        from aiocache.serializers import StringSerializer
    except ImportError:
        logger.warning("aiocache[redis] is not available; falling back to process-local synonyms cache.")
        return None

    redis_url = get_redis_settings().url
    parsed = urlparse(redis_url)
    if parsed.scheme not in {"redis", "rediss"}:
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
        return cache_factory(cache_factory.REDIS, **redis_kwargs)
    except Exception as exc:
        logger.warning(f"Failed to configure Redis synonym cache: {exc}")
        return None
