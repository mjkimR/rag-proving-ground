from typing import Annotated, Any

from app.features.knowledge.knowledge_bases.models import KnowledgeBase
from app.features.knowledge.knowledge_bases.repos import KnowledgeBaseRepository
from app.features.knowledge.knowledge_bases.schemas import (
    KnowledgeBaseCreate,
    KnowledgeBasePatch,
    KnowledgeBasePut,
)
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
    knowledge_embedding_config_hash,
    knowledge_embedding_config_payload,
    resolve_knowledge_embedding_config,
)


class KnowledgeBaseContextKwargs(BaseContextKwargs):
    pass


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

    def _prepare_create_fields(
        self, obj_data: BaseModel, context: KnowledgeBaseContextKwargs, **update_fields: Any
    ) -> dict[str, Any]:
        return _prepare_embedding_config_fields(obj_data, update_fields=update_fields)

    def _prepare_update_fields(
        self,
        obj_data: BaseModel,
        context: KnowledgeBaseContextKwargs,
        partial: bool = True,
        **update_fields: Any,
    ) -> dict[str, Any]:
        if partial and "embedding_config" not in obj_data.model_fields_set:
            return update_fields
        return _prepare_embedding_config_fields(obj_data, update_fields=update_fields)

    async def update(
        self,
        session: Any,
        db_obj: KnowledgeBase,
        obj_in: KnowledgeBasePut | KnowledgeBasePatch,
        context: KnowledgeBaseContextKwargs | None = None,
        **kwargs: Any,
    ) -> KnowledgeBase:
        # Override the update method to inject the existing language if not present in the payload
        context = context or self.context_model()
        partial = isinstance(obj_in, KnowledgeBasePatch)
        update_fields = obj_in.model_dump(exclude_unset=partial)

        if "embedding_config" in update_fields:
            # Re-resolve embedding config using the payload's language, or fallback to the DB's language
            language_value = update_fields.get("language") if "language" in update_fields else db_obj.language
            embedding_config_value = update_fields.get("embedding_config")
            embedding_config = resolve_knowledge_embedding_config(embedding_config_value, language=language_value)
            update_fields["embedding_config"] = knowledge_embedding_config_payload(embedding_config)
            update_fields["embed_config_hash"] = knowledge_embedding_config_hash(embedding_config)

        update_fields = self._prepare_update_fields(obj_in, context, partial=partial, **update_fields)
        return await self.repo.update(session, db_obj, update_fields, **kwargs)


def _prepare_embedding_config_fields(obj_data: BaseModel, *, update_fields: dict[str, Any]) -> dict[str, Any]:
    embedding_config_value = getattr(obj_data, "embedding_config", None)
    language_value = getattr(obj_data, "language", None)
    embedding_config = resolve_knowledge_embedding_config(embedding_config_value, language=language_value)
    update_fields["embedding_config"] = knowledge_embedding_config_payload(embedding_config)
    update_fields["embed_config_hash"] = knowledge_embedding_config_hash(embedding_config)
    return update_fields
