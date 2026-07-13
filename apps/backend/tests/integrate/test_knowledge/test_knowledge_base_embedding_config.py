"""
EmbeddingConfigHook: the service resolves embedding_config / embed_config_hash.

Both columns are nullable and ``embedding_config`` is also a plain create/patch
schema field, so a hook that silently stops running still leaves a written row
behind. ``embed_config_hash`` is the one value only the hook can produce, which
is what these tests pin.

Rows are seeded through the repository (``make_db``), never through the service,
so the starting state holds even if the hook is broken.
"""

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from app.features.knowledge.knowledge_bases.repos import KnowledgeBaseRepository
from app.features.knowledge.knowledge_bases.schemas import KnowledgeBaseCreate, KnowledgeBasePatch
from app.features.knowledge.knowledge_bases.services import KnowledgeBaseService
from rag_core.embeddings import KnowledgeEmbeddingConfig, KnowledgeLanguage
from sqlalchemy.ext.asyncio import AsyncSession

STALE_HASH = "stale-hash-from-a-previous-config"

# The column stores the canonical dict; the schemas take the model. Same values.
CONFIG = {"model": "test-embedding", "distance": "cosine"}
OTHER_CONFIG = {"model": "other-embedding", "distance": "cosine"}


@pytest.fixture
def service() -> KnowledgeBaseService:
    return KnowledgeBaseService(KnowledgeBaseRepository())


@pytest.fixture
def seed_kb(make_db: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """A knowledge base written straight to the DB, carrying a hash the hook must replace."""

    async def _seed(**overrides: Any):
        return await make_db(
            KnowledgeBaseRepository,
            name="kb",
            language=KnowledgeLanguage.EN,
            embedding_config=dict(CONFIG),
            _create_kwargs={"embed_config_hash": STALE_HASH},
            **overrides,
        )

    return _seed


async def test_create_resolves_the_embedding_config_and_its_hash(
    service: KnowledgeBaseService,
    session: AsyncSession,
) -> None:
    kb = await service.create(
        session,
        KnowledgeBaseCreate(name="kb", embedding_config=KnowledgeEmbeddingConfig.model_validate(CONFIG)),
    )

    assert kb.embedding_config is not None
    assert kb.embedding_config["model"] == "test-embedding"
    assert kb.embed_config_hash, "the hash identifies the vector collection and must be set on create"


async def test_patching_only_the_language_keeps_the_stored_embedding_config(
    service: KnowledgeBaseService,
    session: AsyncSession,
    seed_kb: Callable[..., Awaitable[Any]],
) -> None:
    """
    The patch names no embedding_config, so the hook has to read the stored one
    back out of the row. Were it to fall through to None, the model would be
    re-resolved to the deployment default rather than the one this knowledge
    base was built with.
    """
    kb = await seed_kb()

    updated = await service.patch(session, kb.id, KnowledgeBasePatch(language=KnowledgeLanguage.KO))

    assert updated is not None
    assert updated.language == KnowledgeLanguage.KO
    assert updated.embedding_config is not None
    assert updated.embedding_config["model"] == "test-embedding"
    assert updated.embed_config_hash not in (None, STALE_HASH), "the hook must recompute the hash"


async def test_patching_an_unrelated_field_leaves_the_embedding_config_untouched(
    service: KnowledgeBaseService,
    session: AsyncSession,
    seed_kb: Callable[..., Awaitable[Any]],
) -> None:
    """A patch naming neither language nor embedding_config must not rewrite either column."""
    kb = await seed_kb()

    updated = await service.patch(session, kb.id, KnowledgeBasePatch(name="renamed"))

    assert updated is not None
    assert updated.name == "renamed"
    assert updated.embedding_config == CONFIG
    assert updated.embed_config_hash == STALE_HASH


async def test_patching_the_embedding_config_rewrites_the_hash(
    service: KnowledgeBaseService,
    session: AsyncSession,
    seed_kb: Callable[..., Awaitable[Any]],
) -> None:
    kb = await seed_kb()

    updated = await service.patch(
        session,
        kb.id,
        KnowledgeBasePatch(embedding_config=KnowledgeEmbeddingConfig.model_validate(OTHER_CONFIG)),
    )

    assert updated is not None
    assert updated.embedding_config is not None
    assert updated.embedding_config["model"] == "other-embedding"
    assert updated.embed_config_hash not in (None, STALE_HASH), "a new config must produce a new hash"
