"""Embedding configuration schemas and collection naming helpers."""

import hashlib
import json
from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from rag_core.config import get_litellm_settings

KNOWLEDGE_VECTOR_COLLECTION_PREFIX = "vector_store"
KNOWLEDGE_EMBEDDING_HASH_LENGTH = 16


class EmbeddingDistanceMetric(StrEnum):
    """Supported vector distance metrics for knowledge embeddings."""

    COSINE = "cosine"
    DOT = "dot"
    EUCLID = "euclid"


class KnowledgeEmbeddingConfig(BaseModel):
    """Embedding settings that define a physical vector index."""

    model_config = ConfigDict(extra="forbid")

    model: str | None = Field(
        default=None,
        description="LiteLLM embedding model name. Defaults to LITELLM_DEFAULT_EMBEDDING_MODEL when omitted.",
    )
    distance: EmbeddingDistanceMetric = Field(
        default=EmbeddingDistanceMetric.COSINE,
        description="Vector distance metric used by the vector store collection.",
    )

    @field_validator("model")
    @classmethod
    def normalize_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Embedding model name cannot be empty.")
        return normalized


KnowledgeEmbeddingConfigInput = KnowledgeEmbeddingConfig | Mapping[str, Any] | None


def resolve_knowledge_embedding_config(
    config: KnowledgeEmbeddingConfigInput = None,
    *,
    default_model: str | None = None,
) -> KnowledgeEmbeddingConfig:
    """Validate and resolve a knowledge embedding config with runtime defaults."""

    embedding_config = _validate_knowledge_embedding_config(config)
    model = embedding_config.model or default_model or get_litellm_settings().default_embedding_model
    return embedding_config.model_copy(update={"model": model})


def knowledge_embedding_config_payload(config: KnowledgeEmbeddingConfig) -> dict[str, str]:
    """Return the canonical JSON payload persisted and hashed for an embedding config."""

    if config.model is None:
        raise ValueError("Knowledge embedding config must be resolved before creating a payload.")
    return {
        "model": config.model,
        "distance": config.distance.value,
    }


def knowledge_embedding_config_hash(config: KnowledgeEmbeddingConfig) -> str:
    """Create the stable hash used to identify a physical vector collection."""

    serialized = json.dumps(
        knowledge_embedding_config_payload(config),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:KNOWLEDGE_EMBEDDING_HASH_LENGTH]


def knowledge_vector_collection_name(embed_config_hash: str) -> str:
    """Build the physical vector collection name for a knowledge embedding config hash."""

    if not embed_config_hash:
        raise ValueError("Embedding config hash cannot be empty.")
    return f"{KNOWLEDGE_VECTOR_COLLECTION_PREFIX}_{embed_config_hash}"


def _validate_knowledge_embedding_config(config: KnowledgeEmbeddingConfigInput) -> KnowledgeEmbeddingConfig:
    if isinstance(config, KnowledgeEmbeddingConfig):
        return config
    if config is None:
        return KnowledgeEmbeddingConfig()
    return KnowledgeEmbeddingConfig.model_validate(config)


COLPALI_MODELS: set[str] = {
    "vidore/colpali-v1.2-merged",
    "vidore/colSmol-500M-merged",
}


def is_colpali_model(model_name: str | None) -> bool:
    """Check if the embedding model is a ColPali model."""
    return model_name in COLPALI_MODELS if model_name else False
