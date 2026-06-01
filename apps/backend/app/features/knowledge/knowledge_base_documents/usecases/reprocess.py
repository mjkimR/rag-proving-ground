from typing import Annotated
from uuid import UUID

from app.features.knowledge.knowledge_base_documents.facade.pipeline import (
    KnowledgeDocumentPipelineService,
    load_parsed_document_from_storage,
)
from app.features.knowledge.knowledge_base_documents.schemas import (
    KnowledgeBaseDocumentReprocessMode,
    KnowledgeBaseDocumentStatus,
)
from app.features.knowledge.knowledge_base_documents.services import KnowledgeBaseDocumentService
from app.features.knowledge.knowledge_bases.services import KnowledgeBaseService
from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends, HTTPException, status
from rag_core.embeddings import resolve_knowledge_embedding_config


class ReprocessKnowledgeBaseDocumentUseCase(BaseUseCase):
    def __init__(
        self,
        kb_service: Annotated[KnowledgeBaseService, Depends()],
        doc_service: Annotated[KnowledgeBaseDocumentService, Depends()],
        pipeline_service: Annotated[KnowledgeDocumentPipelineService, Depends()],
    ) -> None:
        self.kb_service = kb_service
        self.doc_service = doc_service
        self.pipeline_service = pipeline_service

    async def execute(
        self,
        document_id: UUID,
        mode: KnowledgeBaseDocumentReprocessMode = KnowledgeBaseDocumentReprocessMode.AUTO,
    ) -> dict:
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

            filename = doc.name
            knowledge_base_id = doc.knowledge_base_id
            resolved_chunking_config = (
                doc.chunking_config if doc.chunking_config is not None else kb.default_chunking_config
            )
            embedding_config = resolve_knowledge_embedding_config(kb.embedding_config)
            previous_embed_config_hash = kb.embed_config_hash

        parsed_doc = await load_parsed_document_from_storage(parsed_data_path)
        chunks = await self.pipeline_service.rebuild_chunks(
            document_id=document_id,
            filename=filename,
            parsed_doc=parsed_doc,
            chunking_config=resolved_chunking_config,
            record_history=reprocess_mode == KnowledgeBaseDocumentReprocessMode.RECHUNK,
            history_name_prefix="Rechunk",
            failure_detail_prefix="Document reprocessing",
        )
        await self.pipeline_service.embed_chunks(
            document_id=document_id,
            filename=filename,
            knowledge_base_id=knowledge_base_id,
            chunks=chunks,
            embedding_config=embedding_config,
            previous_embed_config_hash=previous_embed_config_hash,
            history_name_prefix="Reembedding",
            failure_detail_prefix="Document reprocessing",
        )

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
