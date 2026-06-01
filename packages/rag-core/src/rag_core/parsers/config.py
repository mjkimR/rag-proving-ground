"""Parser configuration schemas and cache key helpers."""

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from rag_core.config import get_parser_settings

KNOWLEDGE_PARSING_HASH_LENGTH = 16


class KnowledgeParsingConfig(BaseModel):
    """Parser settings that define a reusable parsed document artifact."""

    model_config = ConfigDict(extra="allow")

    provider: str | None = Field(
        default=None,
        description="Parser provider name. Defaults to PARSER_PROVIDER when omitted.",
    )

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Parser provider cannot be empty.")
        return normalized


KnowledgeParsingConfigInput = KnowledgeParsingConfig | Mapping[str, Any] | None


def resolve_knowledge_parsing_config(
    config: KnowledgeParsingConfigInput = None,
    *,
    provider_override: str | None = None,
    default_provider: str | None = None,
) -> KnowledgeParsingConfig:
    """Validate and resolve parser config with provider override/defaults."""

    parsing_config = _validate_knowledge_parsing_config(config)
    provider = provider_override or parsing_config.provider or default_provider or get_parser_settings().provider
    return parsing_config.model_copy(update={"provider": provider})


def knowledge_parsing_config_payload(config: KnowledgeParsingConfig) -> dict[str, Any]:
    """Return the canonical JSON payload persisted and hashed for parser config."""

    if config.provider is None:
        raise ValueError("Knowledge parsing config must be resolved before creating a payload.")
    return config.model_dump(mode="json", exclude_none=True)


def knowledge_parsing_config_hash(config: KnowledgeParsingConfig) -> str:
    """Create the stable hash used to identify a parsed document artifact."""

    serialized = json.dumps(
        knowledge_parsing_config_payload(config),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:KNOWLEDGE_PARSING_HASH_LENGTH]


def _validate_knowledge_parsing_config(config: KnowledgeParsingConfigInput) -> KnowledgeParsingConfig:
    if isinstance(config, KnowledgeParsingConfig):
        return config
    if config is None:
        return KnowledgeParsingConfig()
    return KnowledgeParsingConfig.model_validate(config)
