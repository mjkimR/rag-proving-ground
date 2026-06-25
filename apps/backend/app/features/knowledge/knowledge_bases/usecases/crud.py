import asyncio
from dataclasses import dataclass
from typing import Annotated, Any, cast
from uuid import UUID

from app.features.knowledge.knowledge_base_documents.models import KnowledgeBaseDocument
from app.features.knowledge.knowledge_base_documents.schemas import (
    ChunkDocumentMessage,
    EmbedDocumentMessage,
    KnowledgeBaseDocumentStatus,
    TaskPriority,
)
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
from app.features.knowledge.knowledge_bases.status import refresh_knowledge_base_status
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
from rag_core.chunkers import resolve_chunking_config
from rag_core.embeddings import (
    KnowledgeLanguage,
    knowledge_embedding_config_payload,
    resolve_knowledge_embedding_config,
)
from rag_core.parsers import resolve_knowledge_parsing_config
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
        self._pending_reprocess = ([], None)

    async def _execute(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: KnowledgeBasePatch,
        context: KnowledgeBaseContextKwargs | None,
    ) -> KnowledgeBase | None:
        updated_kb, docs_to_reprocess, target_status = await _update_knowledge_base_with_document_transitions(
            session=session,
            kb_service=self.service,
            doc_service=self.doc_service,
            obj_pk=obj_pk,
            obj_data=obj_data,
            partial=True,
            context=context,
        )
        self._pending_reprocess = (docs_to_reprocess, target_status)
        return updated_kb

    async def execute(self, *args, **kwargs) -> KnowledgeBase | None:
        self._pending_reprocess = ([], None)
        updated_kb = await super().execute(*args, **kwargs)

        docs_to_reprocess, target_status = self._pending_reprocess
        if updated_kb and docs_to_reprocess and target_status:
            await _trigger_documents_reprocessing(docs_to_reprocess, target_status)

        return updated_kb


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
        self._pending_reprocess = ([], None)

    async def _execute(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: KnowledgeBasePut,
        context: KnowledgeBaseContextKwargs | None,
    ) -> KnowledgeBase | None:
        updated_kb, docs_to_reprocess, target_status = await _update_knowledge_base_with_document_transitions(
            session=session,
            kb_service=self.service,
            doc_service=self.doc_service,
            obj_pk=obj_pk,
            obj_data=obj_data,
            partial=False,
            context=context,
        )
        self._pending_reprocess = (docs_to_reprocess, target_status)
        return updated_kb

    async def execute(self, *args, **kwargs) -> KnowledgeBase | None:
        self._pending_reprocess = ([], None)
        updated_kb = await super().execute(*args, **kwargs)

        docs_to_reprocess, target_status = self._pending_reprocess
        if updated_kb and docs_to_reprocess and target_status:
            await _trigger_documents_reprocessing(docs_to_reprocess, target_status)

        return updated_kb


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
    def has_changes_reprocess(self) -> bool:
        # Reprocessing is needed if parsing, chunking, or embedding changes.
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


@dataclass(frozen=True)
class ReprocessDocumentInfo:
    id: UUID
    knowledge_base_id: UUID
    file_hash: str
    name: str
    content_type: str | None
    priority: TaskPriority = TaskPriority.LOW


async def _update_knowledge_base_with_document_transitions(
    *,
    session: AsyncSession,
    kb_service: KnowledgeBaseService,
    doc_service: KnowledgeBaseDocumentService,
    obj_pk: PrimaryKeyType,
    obj_data: KnowledgeBasePut | KnowledgeBasePatch,
    partial: bool,
    context: KnowledgeBaseContextKwargs | None,
) -> tuple[KnowledgeBase | None, list[ReprocessDocumentInfo], KnowledgeBaseDocumentStatus | None]:
    kb = await kb_service.repo.get_by_pk(session, obj_pk)
    if not kb:
        return None, [], None

    if context is None:
        context = {}
    context.setdefault("_current_language", kb.language)
    context.setdefault("_current_embedding_config", kb.embedding_config)

    change_set = _detect_config_changes(kb, obj_data, partial=partial)
    apply_mode = getattr(obj_data, "apply_mode", KnowledgeBaseConfigApplyMode.INHERITED_ONLY)
    if change_set.embedding_changed and apply_mode == KnowledgeBaseConfigApplyMode.NEW_ONLY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Embedding config changes cannot use NEW_ONLY because existing documents cannot freeze a KB-level vector collection.",
        )

    updated_docs = []
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
        updated_kb = await kb_service.patch(session, obj_pk, cast(KnowledgeBasePatch, obj_data), context=context)
    else:
        updated_kb = await kb_service.put(session, obj_pk, cast(KnowledgeBasePut, obj_data), context=context)

    if updated_kb and change_set.has_changes:
        await refresh_knowledge_base_status(session, kb_service, doc_service, updated_kb.id)

    reprocess_infos = [
        ReprocessDocumentInfo(
            id=doc.id,
            knowledge_base_id=doc.knowledge_base_id,
            file_hash=doc.file_hash,
            name=doc.name,
            content_type=doc.document_info.get("content_type") if doc.document_info else None,
            priority=TaskPriority(doc.priority),
        )
        for doc in updated_docs
    ]

    return updated_kb, reprocess_infos, change_set.target_status


async def _trigger_documents_reprocessing(
    docs: list[ReprocessDocumentInfo],
    target_status: KnowledgeBaseDocumentStatus,
) -> None:
    logger.info(f"Triggering reprocessing for {len(docs)} document(s) with target status {target_status}")
    from app.worker.handlers.ingest import handle_chunk, handle_embed

    for doc in docs:
        try:
            if target_status == KnowledgeBaseDocumentStatus.PENDING_REPARSE:
                # DB polling scheduler will automatically pick up the PENDING_REPARSE document.
                logger.info(f"Document {doc.id} marked as PENDING_REPARSE. Will be picked up by DB-polling dispatcher.")
            elif target_status == KnowledgeBaseDocumentStatus.PENDING_RECHUNK:
                logger.info(f"Dispatching chunk task for document {doc.id} (RECHUNK)")
                from app.features.knowledge.knowledge_base_documents.schemas import get_queue_name

                kicker = handle_chunk.kicker().with_labels(queue_name=get_queue_name(doc.priority))
                await kicker.kiq(
                    ChunkDocumentMessage(
                        document_id=doc.id,
                        knowledge_base_id=doc.knowledge_base_id,
                        filename=doc.name,
                        priority=doc.priority,
                    )
                )
            elif target_status == KnowledgeBaseDocumentStatus.PENDING_REEMBED:
                logger.info(f"Dispatching embed task for document {doc.id} (REEMBED)")
                from app.features.knowledge.knowledge_base_documents.schemas import get_queue_name

                kicker = handle_embed.kicker().with_labels(queue_name=get_queue_name(doc.priority))
                await kicker.kiq(
                    EmbedDocumentMessage(
                        document_id=doc.id,
                        knowledge_base_id=doc.knowledge_base_id,
                        filename=doc.name,
                        priority=doc.priority,
                    )
                )
        except Exception as exc:
            logger.error(f"Failed to publish reprocess/ingest message for document {doc.id}: {exc}")


def _detect_config_changes(
    kb: Any,
    obj_data: BaseModel,
    *,
    partial: bool,
) -> KnowledgeBaseConfigChangeSet:
    fields_set = obj_data.model_fields_set
    check_all_fields = not partial
    parsing_changed = (check_all_fields or "default_parsing_config" in fields_set) and _parsing_config_value(
        getattr(obj_data, "default_parsing_config", None)
    ) != _parsing_config_value(kb.default_parsing_config)
    chunking_changed = (check_all_fields or "default_chunking_config" in fields_set) and _chunking_config_value(
        getattr(obj_data, "default_chunking_config", None)
    ) != _chunking_config_value(kb.default_chunking_config)
    old_lang = getattr(kb, "language", KnowledgeLanguage.EN)
    new_lang = getattr(obj_data, "language", old_lang) if (check_all_fields or "language" in fields_set) else old_lang
    embedding_changed = (
        check_all_fields or "embedding_config" in fields_set or "language" in fields_set
    ) and _embedding_config_value(
        getattr(obj_data, "embedding_config", None), language=new_lang
    ) != _embedding_config_value(kb.embedding_config, language=old_lang)
    return KnowledgeBaseConfigChangeSet(
        parsing_changed=parsing_changed,
        chunking_changed=chunking_changed,
        embedding_changed=embedding_changed,
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


def _embedding_config_value(value: Any, language: KnowledgeLanguage | str = KnowledgeLanguage.EN) -> dict[str, Any]:
    return knowledge_embedding_config_payload(resolve_knowledge_embedding_config(value, language=language))


def _parsing_config_value(value: Any) -> dict[str, Any]:
    return resolve_knowledge_parsing_config(value).model_dump(mode="json", exclude_none=True)


def _chunking_config_value(value: Any) -> dict[str, Any]:
    return resolve_chunking_config(value).model_dump(mode="json", exclude_none=True)
