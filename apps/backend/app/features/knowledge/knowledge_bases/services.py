from contextlib import asynccontextmanager
from typing import Annotated, Any, NotRequired

from app.features.knowledge.knowledge_bases.models import KnowledgeBase
from app.features.knowledge.knowledge_bases.repos import KnowledgeBaseRepository
from app.features.knowledge.knowledge_bases.schemas import (
    KnowledgeBaseCreate,
    KnowledgeBasePatch,
    KnowledgeBasePut,
)
from app_layer_base.base.repos.base import PrimaryKeyType
from app_layer_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
    BaseUpdateServiceMixin,
)
from fastapi import Depends
from pydantic import BaseModel
from rag_core.embeddings import (
    KnowledgeLanguage,
    knowledge_embedding_config_hash,
    knowledge_embedding_config_payload,
    resolve_knowledge_embedding_config,
)
from sqlalchemy.ext.asyncio import AsyncSession


class KnowledgeBaseContextKwargs(BaseContextKwargs):
    _current_language: NotRequired[KnowledgeLanguage]
    _current_embedding_config: NotRequired[dict[str, Any] | None]


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

    @property
    def repo(self) -> KnowledgeBaseRepository:
        return self._repo

    @property
    def context_model(self):
        return KnowledgeBaseContextKwargs

    @asynccontextmanager
    async def _context_update(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: BaseModel,
        context: KnowledgeBaseContextKwargs,
        partial: bool = True,
    ):
        async with super()._context_update(session, obj_pk, obj_data, context, partial=partial):
            missing_lang = "_current_language" not in context
            missing_embed = "_current_embedding_config" not in context
            if missing_lang or missing_embed:
                db_obj = await self.repo.get_by_pk(session, obj_pk)
                if db_obj:
                    if missing_lang:
                        context["_current_language"] = db_obj.language
                    if missing_embed:
                        context["_current_embedding_config"] = db_obj.embedding_config
            yield

    def _prepare_create_fields(
        self, obj_data: KnowledgeBaseCreate, context: KnowledgeBaseContextKwargs, **update_fields: Any
    ) -> dict[str, Any]:
        update_fields = super()._prepare_create_fields(obj_data, context, **update_fields)
        language = obj_data.language
        embedding_config_value = obj_data.embedding_config
        return _prepare_embedding_config_fields(embedding_config_value, language=language, update_fields=update_fields)

    def _prepare_update_fields(
        self,
        obj_data: KnowledgeBasePut | KnowledgeBasePatch,
        context: KnowledgeBaseContextKwargs,
        partial: bool = True,
        **update_fields: Any,
    ) -> dict[str, Any]:
        update_fields = super()._prepare_update_fields(obj_data, context, partial=partial, **update_fields)
        has_embed_config = "embedding_config" in obj_data.model_fields_set
        has_language = "language" in obj_data.model_fields_set

        if partial and not has_embed_config and not has_language:
            return update_fields

        if has_language:
            language = obj_data.language if obj_data.language is not None else KnowledgeLanguage.EN
        else:
            language = context.get("_current_language", KnowledgeLanguage.EN)

        if has_embed_config:
            embedding_config_value = obj_data.embedding_config
        else:
            embedding_config_value = context.get("_current_embedding_config")

        return _prepare_embedding_config_fields(embedding_config_value, language=language, update_fields=update_fields)


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
