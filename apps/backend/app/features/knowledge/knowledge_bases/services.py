from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from app_layer_base.base.repos.base import PrimaryKeyType
from app_layer_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
    BaseUpdateServiceMixin,
)
from app_layer_base.base.services.hooks import CreateHook, Operation, UpdateHook
from fastapi import Depends
from pydantic import BaseModel
from rag_core.embeddings import (
    KnowledgeLanguage,
    knowledge_embedding_config_hash,
    knowledge_embedding_config_payload,
    resolve_knowledge_embedding_config,
)

from app.features.knowledge.knowledge_bases.models import KnowledgeBase
from app.features.knowledge.knowledge_bases.repos import KnowledgeBaseRepository
from app.features.knowledge.knowledge_bases.schemas import (
    KnowledgeBaseCreate,
    KnowledgeBasePatch,
    KnowledgeBasePut,
)


class KnowledgeBaseContextKwargs(BaseContextKwargs):
    pass


class EmbeddingConfigHook(
    CreateHook[KnowledgeBase, KnowledgeBaseContextKwargs],
    UpdateHook[KnowledgeBase, KnowledgeBaseContextKwargs],
):
    """
    Derives ``embedding_config`` / ``embed_config_hash`` from the request.

    A partial update may name only one of language / embedding_config, so the
    other is read from the stored row in ``update_context`` and stashed on
    ``op.state`` (per-call scratch space; a caller that already loaded the row
    in the same session makes this fetch an identity-map hit).
    """

    _STATE_LANGUAGE = "embedding_config_current_language"
    _STATE_EMBED_CONFIG = "embedding_config_current_embedding_config"

    @asynccontextmanager
    async def update_context(
        self,
        op: Operation[KnowledgeBaseContextKwargs],
        pk: PrimaryKeyType,
        data: BaseModel,
        partial: bool = True,
    ) -> AsyncIterator[None]:
        db_obj = await op.repo.get_by_pk(op.session, pk)
        if db_obj:
            op.state[self._STATE_LANGUAGE] = KnowledgeLanguage(db_obj.language)
            op.state[self._STATE_EMBED_CONFIG] = db_obj.embedding_config
        yield

    def create_prepare_fields(
        self,
        op: Operation[KnowledgeBaseContextKwargs],
        data: BaseModel,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        assert isinstance(data, KnowledgeBaseCreate)
        return _prepare_embedding_config_fields(data.embedding_config, language=data.language, update_fields=fields)

    def update_prepare_fields(
        self,
        op: Operation[KnowledgeBaseContextKwargs],
        data: BaseModel,
        fields: dict[str, Any],
        partial: bool = True,
    ) -> dict[str, Any]:
        assert isinstance(data, KnowledgeBasePut | KnowledgeBasePatch)
        has_embed_config = "embedding_config" in data.model_fields_set
        has_language = "language" in data.model_fields_set

        if partial and not has_embed_config and not has_language:
            return fields

        if has_language:
            language = data.language if data.language is not None else KnowledgeLanguage.EN
        else:
            language = op.state.get(self._STATE_LANGUAGE, KnowledgeLanguage.EN)

        embedding_config_value = data.embedding_config if has_embed_config else op.state.get(self._STATE_EMBED_CONFIG)

        return _prepare_embedding_config_fields(embedding_config_value, language=language, update_fields=fields)


class KnowledgeBaseService(
    BaseCreateServiceMixin[KnowledgeBaseRepository, KnowledgeBase, KnowledgeBaseCreate, KnowledgeBaseContextKwargs],
    BaseGetMultiServiceMixin[KnowledgeBaseRepository, KnowledgeBase, KnowledgeBaseContextKwargs],
    BaseGetServiceMixin[KnowledgeBaseRepository, KnowledgeBase, KnowledgeBaseContextKwargs],
    BaseUpdateServiceMixin[
        KnowledgeBaseRepository, KnowledgeBase, KnowledgeBasePut, KnowledgeBasePatch, KnowledgeBaseContextKwargs
    ],
    BaseDeleteServiceMixin[KnowledgeBaseRepository, KnowledgeBase, KnowledgeBaseContextKwargs],
):
    def __init__(self, repo: Annotated[KnowledgeBaseRepository, Depends()]):
        self._repo = repo
        self.hooks = (EmbeddingConfigHook(),)

    @property
    def repo(self) -> KnowledgeBaseRepository:
        return self._repo

    @property
    def context_model(self):
        return KnowledgeBaseContextKwargs


def _prepare_embedding_config_fields(
    embedding_config_value: Any,
    *,
    language: KnowledgeLanguage | str = KnowledgeLanguage.EN,
    update_fields: dict[str, Any],
) -> dict[str, Any]:
    embedding_config = resolve_knowledge_embedding_config(embedding_config_value, language=language)
    update_fields["embedding_config"] = knowledge_embedding_config_payload(embedding_config)
    update_fields["embed_config_hash"] = knowledge_embedding_config_hash(embedding_config)
    return update_fields
