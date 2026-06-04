from typing import Annotated
from uuid import UUID

from app.features.knowledge.knowledge_base_documents.schemas import (
    KnowledgeBaseDocumentReprocessMode,
    KnowledgeBaseDocumentStatus,
    ReprocessDocumentMessage,
)
from app.features.knowledge.knowledge_base_documents.services import KnowledgeBaseDocumentService
from app.features.knowledge.knowledge_bases.services import KnowledgeBaseService
from app.features.knowledge.knowledge_bases.status import refresh_knowledge_base_status
from app.worker.broker import broker
from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends, HTTPException, status
from loguru import logger


class ReprocessKnowledgeBaseDocumentUseCase(BaseUseCase):
    def __init__(
        self,
        kb_service: Annotated[KnowledgeBaseService, Depends()],
        doc_service: Annotated[KnowledgeBaseDocumentService, Depends()],
    ) -> None:
        self.kb_service = kb_service
        self.doc_service = doc_service

    async def execute(
        self,
        document_id: UUID,
        mode: KnowledgeBaseDocumentReprocessMode = KnowledgeBaseDocumentReprocessMode.AUTO,
    ) -> dict:
        """Validate status, set to QUEUED, and publish a reprocess message to Redis."""
        async with AsyncTransaction() as session:
            doc = await self.doc_service.repo.get_by_pk(session, document_id)
            if not doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document with ID '{document_id}' not found.",
                )
            kb = await self.kb_service.repo.get_by_pk(session, doc.knowledge_base_id)
            if not kb:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Knowledge base with ID '{doc.knowledge_base_id}' not found.",
                )

            reprocess_mode = resolve_reprocess_mode(mode, doc.status)
            document_info = dict(doc.document_info or {})
            parsed_data_path = document_info.get("parsed_data_path")
            if not parsed_data_path:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Document has no parsed artifact. Upload or reparse the document first.",
                )

            # Update status to QUEUED to signify processing is requested
            doc.status = KnowledgeBaseDocumentStatus.QUEUED
            await refresh_knowledge_base_status(session, self.kb_service, self.doc_service, doc.knowledge_base_id)

        # Publish reprocess message to Redis
        try:
            logger.info(f"Publishing document.reprocess message for document {document_id}")
            await broker.publish(
                ReprocessDocumentMessage(
                    document_id=document_id,
                    mode=reprocess_mode,
                ),
                "document.reprocess",
            )
        except Exception as exc:
            logger.warning(f"Failed to publish reprocess message for doc {document_id}: {exc}")

        async with AsyncTransaction() as session:
            final_doc = await self.doc_service.repo.get_by_pk(session, document_id)
            if not final_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document with ID '{document_id}' not found.",
                )
            return {
                "id": str(final_doc.id),
                "name": final_doc.name,
                "knowledge_base_id": str(final_doc.knowledge_base_id),
                "status": final_doc.status,
                "file_hash": final_doc.file_hash,
                "document_info": final_doc.document_info,
                "parsing_config": final_doc.parsing_config,
                "chunking_config": final_doc.chunking_config,
            }


def resolve_reprocess_mode(
    requested_mode: KnowledgeBaseDocumentReprocessMode,
    document_status: str,
) -> KnowledgeBaseDocumentReprocessMode:
    if requested_mode != KnowledgeBaseDocumentReprocessMode.AUTO:
        return requested_mode

    if document_status == KnowledgeBaseDocumentStatus.PENDING_RECHUNK:
        return KnowledgeBaseDocumentReprocessMode.RECHUNK
    if document_status == KnowledgeBaseDocumentStatus.PENDING_REEMBED:
        return KnowledgeBaseDocumentReprocessMode.REEMBED
    if document_status == KnowledgeBaseDocumentStatus.PENDING_REPARSE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document requires reparse. Parsed-artifact reprocessing cannot satisfy PENDING_REPARSE.",
        )
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Document status '{document_status}' is not pending parsed-artifact reprocessing.",
    )
