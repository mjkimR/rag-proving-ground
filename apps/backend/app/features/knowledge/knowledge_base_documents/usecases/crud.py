import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from app_file_storage import get_storage_client
from app_layer_base.base.repos.base import PrimaryKeyType
from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.base.usecases.crud import (
    BaseCreateUseCase,
    BaseGetMultiUseCase,
    BaseGetUseCase,
    BasePatchUseCase,
    BasePutUseCase,
)
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends, HTTPException, status
from loguru import logger
from rag_core.embeddings import delete_document_vectors, knowledge_vector_collection_name
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.knowledge.knowledge_base_documents.models import KnowledgeBaseDocument
from app.features.knowledge.knowledge_base_documents.schemas import (
    KnowledgeBaseDocumentCreate,
    KnowledgeBaseDocumentPatch,
    KnowledgeBaseDocumentPut,
    KnowledgeBaseDocumentStatus,
)
from app.features.knowledge.knowledge_base_documents.services import (
    KnowledgeBaseDocumentContextKwargs,
    KnowledgeBaseDocumentService,
)
from app.features.knowledge.knowledge_bases.services import KnowledgeBaseService
from app.features.knowledge.knowledge_bases.status import refresh_knowledge_base_status


class GetKnowledgeBaseDocumentUseCase(
    BaseGetUseCase[KnowledgeBaseDocumentService, KnowledgeBaseDocument, KnowledgeBaseDocumentContextKwargs]
):
    def __init__(self, service: Annotated[KnowledgeBaseDocumentService, Depends()]) -> None:
        super().__init__(service)


class GetMultiKnowledgeBaseDocumentUseCase(
    BaseGetMultiUseCase[KnowledgeBaseDocumentService, KnowledgeBaseDocument, KnowledgeBaseDocumentContextKwargs]
):
    def __init__(self, service: Annotated[KnowledgeBaseDocumentService, Depends()]) -> None:
        super().__init__(service)


class CreateKnowledgeBaseDocumentUseCase(
    BaseCreateUseCase[
        KnowledgeBaseDocumentService,
        KnowledgeBaseDocument,
        KnowledgeBaseDocumentCreate,
        KnowledgeBaseDocumentContextKwargs,
    ]
):
    def __init__(
        self,
        service: Annotated[KnowledgeBaseDocumentService, Depends()],
        kb_service: Annotated[KnowledgeBaseService, Depends()],
    ) -> None:
        super().__init__(service)
        self.kb_service = kb_service

    async def _post_execute(
        self,
        session: AsyncSession,
        obj: KnowledgeBaseDocument,
        obj_data: KnowledgeBaseDocumentCreate,
        context: KnowledgeBaseDocumentContextKwargs | None,
    ) -> KnowledgeBaseDocument:
        await refresh_knowledge_base_status(session, self.kb_service, self.service, obj.knowledge_base_id)
        return obj


class PatchKnowledgeBaseDocumentUseCase(
    BasePatchUseCase[
        KnowledgeBaseDocumentService,
        KnowledgeBaseDocument,
        KnowledgeBaseDocumentPut,
        KnowledgeBaseDocumentPatch,
        KnowledgeBaseDocumentContextKwargs,
    ]
):
    def __init__(
        self,
        service: Annotated[KnowledgeBaseDocumentService, Depends()],
        kb_service: Annotated[KnowledgeBaseService, Depends()],
    ) -> None:
        super().__init__(service)
        self.kb_service = kb_service

    async def _execute(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: KnowledgeBaseDocumentPatch,
        context: KnowledgeBaseDocumentContextKwargs | None,
    ) -> KnowledgeBaseDocument | None:
        doc = await self.service.patch(session, obj_pk, obj_data, context=context)
        if doc and "status" in obj_data.model_fields_set:
            await refresh_knowledge_base_status(session, self.kb_service, self.service, doc.knowledge_base_id)
        return doc


class PutKnowledgeBaseDocumentUseCase(
    BasePutUseCase[
        KnowledgeBaseDocumentService,
        KnowledgeBaseDocument,
        KnowledgeBaseDocumentPut,
        KnowledgeBaseDocumentPatch,
        KnowledgeBaseDocumentContextKwargs,
    ]
):
    def __init__(
        self,
        service: Annotated[KnowledgeBaseDocumentService, Depends()],
        kb_service: Annotated[KnowledgeBaseService, Depends()],
    ) -> None:
        super().__init__(service)
        self.kb_service = kb_service

    async def _execute(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: KnowledgeBaseDocumentPut,
        context: KnowledgeBaseDocumentContextKwargs | None,
    ) -> KnowledgeBaseDocument | None:
        doc = await self.service.put(session, obj_pk, obj_data, context=context)
        if doc:
            await refresh_knowledge_base_status(session, self.kb_service, self.service, doc.knowledge_base_id)
        return doc


class DeleteKnowledgeBaseDocumentUseCase(BaseUseCase):
    def __init__(
        self,
        service: Annotated[KnowledgeBaseDocumentService, Depends()],
        kb_service: Annotated[KnowledgeBaseService, Depends()],
    ) -> None:
        self.service = service
        self.kb_service = kb_service

    async def execute(self, document_id: UUID, context: KnowledgeBaseDocumentContextKwargs | None = None) -> dict:
        async with AsyncTransaction() as session:
            doc = await self.service.repo.get_by_pk(session, document_id)
            if not doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document with ID '{document_id}' not found.",
                )

            kb = await self.kb_service.repo.get_by_pk(session, doc.knowledge_base_id)
            cleanup_target = KnowledgeDocumentCleanupTarget(
                document_id=doc.id,
                file_hash=doc.file_hash,
                knowledge_base_id=doc.knowledge_base_id,
                knowledge_base_name=kb.name if kb else "unknown",
                embed_config_hash=kb.embed_config_hash if kb else None,
            )
            knowledge_base_id = doc.knowledge_base_id
            doc.status = KnowledgeBaseDocumentStatus.DELETING
            await session.flush()
            await refresh_knowledge_base_status(session, self.kb_service, self.service, knowledge_base_id)

        cleanup_errors = await cleanup_knowledge_document_assets(cleanup_target)
        if cleanup_errors:
            async with AsyncTransaction() as session:
                await self.service.repo.update_by_pk(
                    session, document_id, {"status": KnowledgeBaseDocumentStatus.FAILED}
                )
                await refresh_knowledge_base_status(session, self.kb_service, self.service, knowledge_base_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to clean up document assets: {'; '.join(cleanup_errors)}",
            )

        async with AsyncTransaction() as session:
            success = await self.service.repo.delete_by_pk(session, document_id)
            await refresh_knowledge_base_status(session, self.kb_service, self.service, knowledge_base_id)
            return {
                "status": "success" if success else "failed",
                "message": "Successfully deleted document and all associated assets.",
            }


@dataclass(frozen=True)
class KnowledgeDocumentCleanupTarget:
    document_id: UUID
    file_hash: str
    knowledge_base_id: UUID
    knowledge_base_name: str
    embed_config_hash: str | None = None


async def cleanup_knowledge_document_assets(target: KnowledgeDocumentCleanupTarget) -> list[str]:
    errors: list[str] = []
    cleanup_tasks: list[Awaitable[str | None]] = []
    if target.embed_config_hash:
        cleanup_tasks.append(_cleanup_vector_store_assets(target))
    cleanup_tasks.append(_cleanup_storage_assets(target))

    results = await asyncio.gather(*cleanup_tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            logger.opt(exception=result).error(f"Unexpected cleanup failure for doc {target.document_id}.")
            errors.append(f"unexpected cleanup failure for document {target.document_id}: {result}")
        elif result is not None:
            errors.append(result)
    return errors


async def _cleanup_vector_store_assets(target: KnowledgeDocumentCleanupTarget) -> str | None:
    try:
        if not target.embed_config_hash:
            return None
        collection_name = knowledge_vector_collection_name(target.embed_config_hash)
        await delete_document_vectors(collection_name, target.document_id)
    except Exception as exc:
        logger.exception(f"Failed to delete points from vector store for doc {target.document_id}: {exc}")
        return f"vector store cleanup failed for document {target.document_id}: {exc}"
    return None


async def _cleanup_storage_assets(target: KnowledgeDocumentCleanupTarget) -> str | None:
    try:
        storage_client = get_storage_client()
        prefix = f"knowledge/{target.knowledge_base_id}/{target.file_hash}/"
        async for file_path in storage_client.list_files(prefix):
            await storage_client.delete_file(file_path)
    except Exception as exc:
        logger.exception(f"Failed to delete storage assets for doc {target.document_id}: {exc}")
        return f"storage cleanup failed for document {target.document_id}: {exc}"
    return None
