"""Application configuration helpers."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LiteLLMSettings(BaseSettings):
    """Settings for models served through the local LiteLLM gateway."""

    base_url: str = Field(default="http://localhost:4000/v1", validation_alias="LITELLM_BASE_URL")
    api_key: SecretStr = Field(default="sk-local", validation_alias="LITELLM_API_KEY")  # type: ignore
    temperature: float | None = Field(default=None, validation_alias="LITELLM_TEMPERATURE")
    max_tokens: int | None = Field(default=None, validation_alias="LITELLM_MAX_TOKENS")
    timeout: float | None = Field(default=60.0, validation_alias="LITELLM_TIMEOUT")
    max_retries: int = Field(default=2, validation_alias="LITELLM_MAX_RETRIES")

    # default models
    default_llm_model: str = Field(default="gpt-oss-20b", validation_alias="LITELLM_DEFAULT_LLM_MODEL")
    default_embedding_model: str = Field(default="vllm-embedding", validation_alias="LITELLM_DEFAULT_EMBEDDING_MODEL")
    default_reranker_model: str = Field(default="vllm-reranker", validation_alias="LITELLM_DEFAULT_RERANKER_MODEL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class ParserSettings(BaseSettings):
    """Settings for document parser adapters."""

    provider: str = Field(default="docling", validation_alias="PARSER_PROVIDER")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class NativeTextParserSettings(BaseSettings):
    """Settings used by the Native Text parser provider."""

    max_page_chars: int = Field(
        default=2000,
        validation_alias="NATIVE_MAX_PAGE_CHARS",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class HTTPClientSettings(BaseSettings):
    """
    Settings for the global HTTP client (httpx).
    Defaults match httpx standard defaults.
    """

    timeout: float = Field(
        default=5.0,
        description="Default timeout in seconds for HTTP requests",
        validation_alias="HTTP_TIMEOUT",
    )
    max_connections: int = Field(
        default=100,
        description="Maximum number of concurrent HTTP connections in the connection pool",
        validation_alias="HTTP_MAX_CONNECTIONS",
    )
    max_keepalive_connections: int = Field(
        default=20,
        description="Maximum number of keep-alive connections to maintain in the pool",
        validation_alias="HTTP_MAX_KEEPALIVE_CONNECTIONS",
    )
    keepalive_expiry: float = Field(
        default=5.0,
        description="Time in seconds before an idle keep-alive connection is closed",
        validation_alias="HTTP_KEEPALIVE_EXPIRY",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_litellm_settings() -> LiteLLMSettings:
    return LiteLLMSettings()


@lru_cache
def get_parser_settings() -> ParserSettings:
    return ParserSettings()


@lru_cache
def get_native_text_parser_settings() -> NativeTextParserSettings:
    return NativeTextParserSettings()


@lru_cache
def get_http_client_settings() -> HTTPClientSettings:
    return HTTPClientSettings()


class RedisSettings(BaseSettings):
    """Settings for Redis connection (FastStream broker)."""

    url: str = Field(default="redis://localhost:16379/0", validation_alias="REDIS_URL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_redis_settings() -> RedisSettings:
    return RedisSettings()


class RabbitMQSettings(BaseSettings):
    """Settings for RabbitMQ connection (Taskiq broker)."""

    url: str = Field(default="amqp://guest:guest@localhost:5672/", validation_alias="RABBITMQ_URL")
    parse_queue_name: str = Field(default="kb_ingest_parse", validation_alias="RABBITMQ_QUEUE_NAME")
    chunk_queue_name: str = Field(default="kb_ingest_chunk", validation_alias="RABBITMQ_CHUNK_QUEUE_NAME")
    embed_queue_name: str = Field(default="kb_ingest_embed", validation_alias="RABBITMQ_EMBED_QUEUE_NAME")
    max_priority: int = Field(default=5, validation_alias="RABBITMQ_MAX_PRIORITY")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_rabbitmq_settings() -> RabbitMQSettings:
    return RabbitMQSettings()


class SynonymCacheSettings(BaseSettings):
    """Settings for shared synonym expansion cache."""

    enabled: bool = Field(default=True, validation_alias="SYNONYM_CACHE_ENABLED")
    local_fallback_ttl_seconds: int = Field(
        default=10,
        ge=1,
        validation_alias="SYNONYM_CACHE_LOCAL_FALLBACK_TTL_SECONDS",
    )
    version_check_ttl_seconds: int = Field(
        default=5,
        ge=1,
        validation_alias="SYNONYM_CACHE_VERSION_CHECK_TTL_SECONDS",
    )
    namespace: str = Field(default="rag_core", validation_alias="SYNONYM_CACHE_NAMESPACE")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_synonym_cache_settings() -> SynonymCacheSettings:
    return SynonymCacheSettings()


class ColPaliSettings(BaseSettings):
    """Settings for ColPali serving engine (Infinity)."""

    base_url: str = Field(default="http://localhost:7997", validation_alias="COLPALI_BASE_URL")
    timeout: float = Field(default=120.0, validation_alias="COLPALI_TIMEOUT")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_colpali_settings() -> ColPaliSettings:
    return ColPaliSettings()


class FastParserSettings(BaseSettings):
    """Settings used for external fast-parser microservice engines."""

    base_url: str = Field(
        default="http://localhost:15002",
        validation_alias="FAST_PARSER_BASE_URL",
    )
    timeout: float = Field(default=120.0, validation_alias="FAST_PARSER_TIMEOUT", gt=0)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_fast_parser_settings() -> FastParserSettings:
    return FastParserSettings()
