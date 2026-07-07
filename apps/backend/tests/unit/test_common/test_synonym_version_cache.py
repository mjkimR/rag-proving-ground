import pytest
from app.common import synonym_version_cache


class RedisSettings:
    url = "redis://:secret@localhost:6380/2"


class CacheSettings:
    enabled = True
    namespace = "test-synonyms"


class DisabledCacheSettings:
    enabled = False
    namespace = "test-synonyms"


def test_build_synonym_version_cache_uses_string_serializer(monkeypatch: pytest.MonkeyPatch) -> None:
    from aiocache.serializers import StringSerializer

    monkeypatch.setattr(synonym_version_cache, "get_redis_settings", lambda: RedisSettings())
    monkeypatch.setattr(synonym_version_cache, "get_synonym_cache_settings", lambda: CacheSettings())

    client = synonym_version_cache.build_synonym_version_cache()

    assert client is not None
    assert isinstance(client.serializer, StringSerializer)


def test_build_synonym_version_cache_returns_none_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(synonym_version_cache, "get_synonym_cache_settings", lambda: DisabledCacheSettings())

    assert synonym_version_cache.build_synonym_version_cache() is None


def test_build_synonym_version_cache_rejects_non_redis_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    class BadSettings:
        url = "http://localhost:1234"

    monkeypatch.setattr(synonym_version_cache, "get_redis_settings", lambda: BadSettings())
    monkeypatch.setattr(synonym_version_cache, "get_synonym_cache_settings", lambda: CacheSettings())

    assert synonym_version_cache.build_synonym_version_cache() is None
