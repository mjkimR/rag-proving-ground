"""Embedding configuration schemas and collection naming helpers."""

import hashlib
import json
from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rag_core.config import get_litellm_settings

KNOWLEDGE_VECTOR_COLLECTION_PREFIX = "vector_store"
KNOWLEDGE_EMBEDDING_HASH_LENGTH = 16


class EmbeddingDistanceMetric(StrEnum):
    """Supported vector distance metrics for knowledge embeddings."""

    COSINE = "cosine"
    DOT = "dot"
    EUCLID = "euclid"


class RetrievalMode(StrEnum):
    """Supported retrieval modes for knowledge search."""

    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"


class SparseEmbeddingModel(StrEnum):
    """Supported sparse embedding models for knowledge search."""

    EN_BM25 = "en-bm25"
    KO_KIWI_BM25 = "ko-kiwi-bm25"


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
    use_colpali: bool = Field(
        default=False,
        description="Whether to use ColPali (vision/multi-vector RAG). Defaults to False.",
    )
    colpali_model: str | None = Field(
        default=None,
        description="ColPali model name to use when use_colpali is True.",
    )
    retrieval_mode: RetrievalMode = Field(
        default=RetrievalMode.DENSE,
        description="Retrieval mode for searching the index. Can be 'dense', 'sparse', or 'hybrid'.",
    )
    sparse_model: str | None = Field(
        default=None,
        description="Sparse embedding model name. e.g. 'Qdrant/bm25' for FastEmbed BM25.",
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

    @model_validator(mode="after")
    def validate_retrieval_mode(self) -> "KnowledgeEmbeddingConfig":
        if self.use_colpali and self.retrieval_mode != RetrievalMode.DENSE:
            raise NotImplementedError("Hybrid or sparse search with ColPali is not implemented yet.")
        return self


KnowledgeEmbeddingConfigInput = KnowledgeEmbeddingConfig | Mapping[str, Any] | None


def resolve_knowledge_embedding_config(
    config: KnowledgeEmbeddingConfigInput = None,
    *,
    default_model: str | None = None,
    language: str = "en",
) -> KnowledgeEmbeddingConfig:
    """Validate and resolve a knowledge embedding config with runtime defaults."""

    embedding_config = _validate_knowledge_embedding_config(config)
    model = embedding_config.model or default_model or get_litellm_settings().default_embedding_model
    colpali_model = None
    if embedding_config.use_colpali:
        colpali_model = embedding_config.colpali_model or "vidore/colpali-v1.2-merged"

    sparse_model = None
    if embedding_config.retrieval_mode in (RetrievalMode.SPARSE, RetrievalMode.HYBRID):
        if not embedding_config.sparse_model:
            sparse_model = (
                SparseEmbeddingModel.KO_KIWI_BM25.value if language == "ko" else SparseEmbeddingModel.EN_BM25.value
            )
        else:
            sparse_model = embedding_config.sparse_model

    return embedding_config.model_copy(
        update={
            "model": model,
            "colpali_model": colpali_model,
            "sparse_model": sparse_model,
        }
    )


def knowledge_embedding_config_payload(config: KnowledgeEmbeddingConfig) -> dict[str, Any]:
    """Return the canonical JSON payload persisted and hashed for an embedding config."""

    if config.model is None:
        raise ValueError("Knowledge embedding config must be resolved before creating a payload.")
    return {
        "model": config.model,
        "distance": config.distance.value,
        "use_colpali": config.use_colpali,
        "colpali_model": config.colpali_model,
        "retrieval_mode": config.retrieval_mode.value,
        "sparse_model": config.sparse_model,
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
    "vidore/colpali-v1.3-merged",
    "vidore/colSmol-500M-merged",
}


def is_colpali_model(model_name: str | None) -> bool:
    """Check if the embedding model is a ColPali model."""
    if not model_name:
        return False
    name_lower = model_name.lower()
    return model_name in COLPALI_MODELS or "colpali" in name_lower or "colsmol" in name_lower
