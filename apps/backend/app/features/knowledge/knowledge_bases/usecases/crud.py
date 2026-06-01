import asyncio
from dataclasses import dataclass
from typing import Annotated, Any, cast
from uuid import UUID

from app.features.knowledge.knowledge_base_documents.models import KnowledgeBaseDocument
from app.features.knowledge.knowledge_base_documents.schemas import KnowledgeBaseDocumentStatus
from app.features.knowledge.knowledge_base_documents.services import KnowledgeBaseDocumentService
from app.features.knowledge.knowledge_base_documents.usecases.crud import (
    KnowledgeDocumentCleanupTarget,
    cleanup_knowledge_document_assets,
)
from app.features.knowledge.knowledge_bases.models import KnowledgeBase
from app.features.knowledge.knowledge_bases.schemas import (
    KnowledgeBaseConfigApplyMode,
    KnowledgeBaseCreate,
    KnowledgeBasePatch,
    KnowledgeBasePut,
    KnowledgeBaseStatus,
)
from app.features.knowledge.knowledge_bases.services import KnowledgeBaseContextKwargs, KnowledgeBaseService
from app_layer_base.base.repos.base import PrimaryKeyType
from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.base.usecases.crud import (
    BaseCreateUseCase,
    BaseGetMultiUseCase,
    BasePatchUseCase,
    BasePutUseCase,
)
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel
from rag_core.embeddings import (
    knowledge_embedding_config_payload,
    resolve_knowledge_embedding_config,
)
from sqlalchemy.ext.asyncio import AsyncSession


class GetKnowledgeBaseUseCase(BaseUseCase):
    def __init__(self, service: Annotated[KnowledgeBaseService, Depends()]) -> None:
        self.service = service

    async def execute(self, knowledge_base_id: UUID) -> KnowledgeBase | None:
        async with AsyncTransaction() as session:
            return await self.service.repo.get_by_pk(session, knowledge_base_id)


class GetMultiKnowledgeBaseUseCase(
    BaseGetMultiUseCase[KnowledgeBaseService, KnowledgeBase, KnowledgeBaseContextKwargs]
):
    def __init__(self, service: Annotated[KnowledgeBaseService, Depends()]) -> None:
        super().__init__(service)


class CreateKnowledgeBaseUseCase(
    BaseCreateUseCase[KnowledgeBaseService, KnowledgeBase, KnowledgeBaseCreate, KnowledgeBaseContextKwargs]
):
    def __init__(self, service: Annotated[KnowledgeBaseService, Depends()]) -> None:
        super().__init__(service)


class PatchKnowledgeBaseUseCase(
    BasePatchUseCase[
        KnowledgeBaseService, KnowledgeBase, KnowledgeBasePut, KnowledgeBasePatch, KnowledgeBaseContextKwargs
    ]
):
    def __init__(
        self,
        service: Annotated[KnowledgeBaseService, Depends()],
        doc_service: Annotated[KnowledgeBaseDocumentService, Depends()],
    ) -> None:
        super().__init__(service)
        self.doc_service = doc_service

    async def _execute(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: KnowledgeBasePatch,
        context: KnowledgeBaseContextKwargs | None,
    ) -> KnowledgeBase | None:
        return await _update_knowledge_base_with_document_transitions(
            session=session,
            kb_service=self.service,
            doc_service=self.doc_service,
            obj_pk=obj_pk,
            obj_data=obj_data,
            partial=True,
            context=context,
        )


class PutKnowledgeBaseUseCase(
    BasePutUseCase[
        KnowledgeBaseService, KnowledgeBase, KnowledgeBasePut, KnowledgeBasePatch, KnowledgeBaseContextKwargs
    ]
):
    def __init__(
        self,
        service: Annotated[KnowledgeBaseService, Depends()],
        doc_service: Annotated[KnowledgeBaseDocumentService, Depends()],
    ) -> None:
        super().__init__(service)
        self.doc_service = doc_service

    async def _execute(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: KnowledgeBasePut,
        context: KnowledgeBaseContextKwargs | None,
    ) -> KnowledgeBase | None:
        return await _update_knowledge_base_with_document_transitions(
            session=session,
            kb_service=self.service,
            doc_service=self.doc_service,
            obj_pk=obj_pk,
            obj_data=obj_data,
            partial=False,
            context=context,
        )


class DeleteKnowledgeBaseUseCase(BaseUseCase):
    def __init__(
        self,
        service: Annotated[KnowledgeBaseService, Depends()],
        doc_service: Annotated[KnowledgeBaseDocumentService, Depends()],
    ) -> None:
        self.service = service
        self.doc_service = doc_service

    async def execute(self, knowledge_base_id: UUID) -> dict:
        async with AsyncTransaction() as session:
            kb = await self.service.repo.get_by_pk(session, knowledge_base_id)
            if not kb:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Knowledge base with ID '{knowledge_base_id}' not found.",
                )

            # Retrieve all documents belonging to this KB
            docs = await self.doc_service.repo.get_all(
                session,
                where=(self.doc_service.repo.model.knowledge_base_id == knowledge_base_id,),
            )
            cleanup_targets = [
                KnowledgeDocumentCleanupTarget(
                    document_id=doc.id,
                    file_hash=doc.file_hash,
                    knowledge_base_name=kb.name,
                    embed_config_hash=kb.embed_config_hash,
                )
                for doc in docs
            ]
            kb.status = KnowledgeBaseStatus.DELETING
            for doc in docs:
                doc.status = KnowledgeBaseDocumentStatus.DELETING
            await session.flush()

        cleanup_errors: list[str] = []
        cleanup_results = await asyncio.gather(
            *(cleanup_knowledge_document_assets(target) for target in cleanup_targets),
            return_exceptions=True,
        )
        for target, cleanup_result in zip(cleanup_targets, cleanup_results, strict=True):
            if isinstance(cleanup_result, BaseException):
                logger.opt(exception=cleanup_result).error(
                    f"Unexpected cleanup failure for document {target.document_id}."
                )
                cleanup_errors.append(f"unexpected cleanup failure for document {target.document_id}: {cleanup_result}")
            else:
                cleanup_errors.extend(cleanup_result)
        if cleanup_errors:
            async with AsyncTransaction() as session:
                await self.service.repo.update_by_pk(session, knowledge_base_id, {"status": KnowledgeBaseStatus.FAILED})
                for target in cleanup_targets:
                    await self.doc_service.repo.update_by_pk(
                        session, target.document_id, {"status": KnowledgeBaseDocumentStatus.FAILED}
                    )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to clean up knowledge base assets: {'; '.join(cleanup_errors)}",
            )

        async with AsyncTransaction() as session:
            success = await self.service.repo.delete_by_pk(session, knowledge_base_id)
            return {
                "status": "success" if success else "failed",
                "message": "Successfully deleted knowledge base and all associated child assets.",
            }


@dataclass(frozen=True)
class KnowledgeBaseConfigChangeSet:
    parsing_changed: bool = False
    chunking_changed: bool = False
    embedding_changed: bool = False

    @property
    def has_changes(self) -> bool:
        return self.parsing_changed or self.chunking_changed or self.embedding_changed

    @property
    def target_status(self) -> KnowledgeBaseDocumentStatus | None:
        if self.parsing_changed:
            return KnowledgeBaseDocumentStatus.PENDING_REPARSE
        if self.chunking_changed:
            return KnowledgeBaseDocumentStatus.PENDING_RECHUNK
        if self.embedding_changed:
            return KnowledgeBaseDocumentStatus.PENDING_REEMBED
        return None


async def _update_knowledge_base_with_document_transitions(
    *,
    session: AsyncSession,
    kb_service: KnowledgeBaseService,
    doc_service: KnowledgeBaseDocumentService,
    obj_pk: PrimaryKeyType,
    obj_data: KnowledgeBasePut | KnowledgeBasePatch,
    partial: bool,
    context: KnowledgeBaseContextKwargs | None,
) -> KnowledgeBase | None:
    kb = await kb_service.repo.get_by_pk(session, obj_pk)
    if not kb:
        return None

    change_set = _detect_config_changes(kb, obj_data, partial=partial)
    apply_mode = getattr(obj_data, "apply_mode", KnowledgeBaseConfigApplyMode.INHERITED_ONLY)
    if change_set.embedding_changed and apply_mode == KnowledgeBaseConfigApplyMode.NEW_ONLY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Embedding config changes cannot use NEW_ONLY because existing documents cannot freeze a KB-level vector collection.",
        )

    if change_set.has_changes:
        docs = await doc_service.repo.get_all(
            session,
            where=(doc_service.repo.model.knowledge_base_id == kb.id,),
        )
        updated_docs = _prepare_existing_documents_for_config_update(
            docs=docs,
            kb=kb,
            change_set=change_set,
            apply_mode=apply_mode,
        )
        if updated_docs:
            session.add_all(updated_docs)
            await session.flush()

    if partial:
        return await kb_service.patch(session, obj_pk, cast(KnowledgeBasePatch, obj_data), context=context)
    return await kb_service.put(session, obj_pk, cast(KnowledgeBasePut, obj_data), context=context)


def _detect_config_changes(
    kb: Any,
    obj_data: BaseModel,
    *,
    partial: bool,
) -> KnowledgeBaseConfigChangeSet:
    fields_set = obj_data.model_fields_set
    check_all_fields = not partial
    return KnowledgeBaseConfigChangeSet(
        parsing_changed=(
            (check_all_fields or "default_parsing_config" in fields_set)
            and _json_config_value(getattr(obj_data, "default_parsing_config", None))
            != _json_config_value(kb.default_parsing_config)
        ),
        chunking_changed=(
            (check_all_fields or "default_chunking_config" in fields_set)
            and _json_config_value(getattr(obj_data, "default_chunking_config", None))
            != _json_config_value(kb.default_chunking_config)
        ),
        embedding_changed=(
            (check_all_fields or "embedding_config" in fields_set)
            and _embedding_config_value(getattr(obj_data, "embedding_config", None))
            != _embedding_config_value(kb.embedding_config)
        ),
    )


def _prepare_existing_documents_for_config_update(
    *,
    docs: list[KnowledgeBaseDocument] | Any,
    kb: Any,
    change_set: KnowledgeBaseConfigChangeSet,
    apply_mode: KnowledgeBaseConfigApplyMode,
) -> list[KnowledgeBaseDocument]:
    updated_docs: list[KnowledgeBaseDocument] = []
    if apply_mode == KnowledgeBaseConfigApplyMode.NEW_ONLY:
        return _freeze_inherited_document_configs(docs=docs, kb=kb, change_set=change_set)

    target_status = change_set.target_status
    if target_status is None:
        return updated_docs

    for doc in docs:
        doc_updated = False
        if apply_mode == KnowledgeBaseConfigApplyMode.FORCE_ALL:
            doc_updated |= _set_document_field(doc, "parsing_config", None)
            doc_updated |= _set_document_field(doc, "chunking_config", None)
            doc_updated |= _set_document_field(doc, "status", target_status)
            if doc_updated:
                updated_docs.append(doc)
            continue

        if _document_inherits_changed_config(doc, change_set):
            doc_updated |= _set_document_field(doc, "status", target_status)
        if doc_updated:
            updated_docs.append(doc)

    return updated_docs


def _freeze_inherited_document_configs(
    *,
    docs: list[KnowledgeBaseDocument] | Any,
    kb: Any,
    change_set: KnowledgeBaseConfigChangeSet,
) -> list[KnowledgeBaseDocument]:
    updated_docs: list[KnowledgeBaseDocument] = []
    for doc in docs:
        doc_updated = False
        if change_set.parsing_changed and doc.parsing_config is None:
            doc_updated |= _set_document_field(
                doc,
                "parsing_config",
                _frozen_config_value(kb.default_parsing_config),
            )
        if change_set.chunking_changed and doc.chunking_config is None:
            doc_updated |= _set_document_field(
                doc,
                "chunking_config",
                _frozen_config_value(kb.default_chunking_config),
            )
        if doc_updated:
            updated_docs.append(doc)

    return updated_docs


def _document_inherits_changed_config(doc: KnowledgeBaseDocument, change_set: KnowledgeBaseConfigChangeSet) -> bool:
    if change_set.embedding_changed:
        return True
    if change_set.parsing_changed and doc.parsing_config is None:
        return True
    return bool(change_set.chunking_changed and doc.chunking_config is None)


def _frozen_config_value(value: dict | None) -> dict:
    return dict(value or {})


def _set_document_field(doc: KnowledgeBaseDocument, field_name: str, value: Any) -> bool:
    if getattr(doc, field_name) == value:
        return False
    setattr(doc, field_name, value)
    return True


def _json_config_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _json_config_value(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_json_config_value(item) for item in value]
    return value


def _embedding_config_value(value: Any) -> dict[str, str]:
    return knowledge_embedding_config_payload(resolve_knowledge_embedding_config(value))
