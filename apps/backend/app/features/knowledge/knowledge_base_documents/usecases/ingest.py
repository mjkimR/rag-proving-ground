import hashlib
import os
from typing import Annotated
from uuid import UUID

from app.features.knowledge.knowledge_base_documents.facade.pipeline import knowledge_original_file_key
from app.features.knowledge.knowledge_base_documents.schemas import (
    KnowledgeBaseDocumentCreate,
    KnowledgeBaseDocumentStatus,
    ParseDocumentMessage,
)
from app.features.knowledge.knowledge_base_documents.services import KnowledgeBaseDocumentService
from app.features.knowledge.knowledge_bases.services import KnowledgeBaseService
from app.features.knowledge.knowledge_bases.status import refresh_knowledge_base_status
from app_file_storage import get_storage_client
from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends, HTTPException, UploadFile, status
from loguru import logger

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".pdf", ".html", ".htm", ".md", ".docx", ".txt"}


def file_content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class IngestKnowledgeDocumentUseCase(BaseUseCase):
    def __init__(
        self,
        kb_service: Annotated[KnowledgeBaseService, Depends()],
        doc_service: Annotated[KnowledgeBaseDocumentService, Depends()],
    ):
        self.kb_service = kb_service
        self.doc_service = doc_service

    async def execute(
        self,
        knowledge_base_id: UUID,
        file: UploadFile,
        provider: str | None = None,
    ) -> dict:
        """Validate, upload to MinIO, and queue a document ingestion task, tracking state transitions."""
        # 1. Input validation & sanitization
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file must have a filename.",
            )
        filename = os.path.basename(file.filename)

        _, ext = os.path.splitext(filename.lower())
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: '{ext}'. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

        content = await file.read(MAX_FILE_SIZE + 1)
        if len(content) > MAX_FILE_SIZE:
            logger.warning(f"File upload blocked: {filename} exceeded size limit of 10MB.")
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Uploaded file size exceeds the 10MB limit.",
            )

        file_hash = file_content_hash(content)

        default_parsing_config = None

        # 2. Database record setup (First Transaction: Initialize/Get Document)
        async with AsyncTransaction() as session:
            kb = await self.kb_service.repo.get_by_pk(session, knowledge_base_id)
            if not kb:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Knowledge base with ID '{knowledge_base_id}' not found.",
                )
            default_parsing_config = kb.default_parsing_config

            # Check if document already exists
            existing_docs = await self.doc_service.repo.get_all(
                session,
                where=(
                    self.doc_service.repo.model.knowledge_base_id == knowledge_base_id,
                    self.doc_service.repo.model.file_hash == file_hash,
                ),
            )

            if existing_docs:
                doc = existing_docs[0]
                doc.status = KnowledgeBaseDocumentStatus.QUEUED
                doc.name = filename
                doc_info = dict(doc.document_info or {})
                doc_info.update(
                    {
                        "filename": filename,
                        "size_bytes": len(content),
                        "content_type": file.content_type,
                    }
                )
                doc.document_info = doc_info
                await session.flush()
            else:
                doc_create = KnowledgeBaseDocumentCreate(
                    name=filename,
                    knowledge_base_id=knowledge_base_id,
                    status=KnowledgeBaseDocumentStatus.QUEUED,
                    file_hash=file_hash,
                    document_info={
                        "filename": filename,
                        "size_bytes": len(content),
                        "content_type": file.content_type,
                    },
                )
                doc = await self.doc_service.create(session, doc_create)

            await refresh_knowledge_base_status(session, self.kb_service, self.doc_service, knowledge_base_id)
            doc_id = doc.id

        # 3. Upload file content to MinIO
        storage_client = get_storage_client()
        original_file_key = knowledge_original_file_key(knowledge_base_id, file_hash, filename)
        try:
            logger.info(f"Uploading file '{filename}' to MinIO path '{original_file_key}'")
            await storage_client.upload_file(original_file_key, content)
        except Exception as exc:
            logger.error(f"Failed to upload document content to storage: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save document to storage: {exc}",
            ) from exc

        # 4. Enqueue parse message to Redis scheduling queue
        try:
            logger.info(f"Queueing document.parse message for document {doc_id}")
            from rag_core.parsers import resolve_knowledge_parsing_config

            resolved_config = resolve_knowledge_parsing_config(default_parsing_config, provider_override=provider)
            resolved_provider = resolved_config.get_provider_for_filename(filename)

            msg = ParseDocumentMessage(
                document_id=doc_id,
                knowledge_base_id=knowledge_base_id,
                file_hash=file_hash,
                filename=filename,
                content_type=file.content_type,
                provider=resolved_provider,
            )

            from app.worker.scheduling import enqueue_parse_document_message

            await enqueue_parse_document_message(knowledge_base_id, msg, resolved_provider)
        except Exception as exc:
            logger.warning(f"Failed to enqueue ingest message for doc {doc_id}: {exc}")

        # 5. Return immediate response
        async with AsyncTransaction() as session:
            final_doc = await self.doc_service.repo.get_by_pk(session, doc_id)
            doc_data = {
                "id": str(final_doc.id) if final_doc else str(doc_id),
                "name": final_doc.name if final_doc else filename,
                "status": final_doc.status if final_doc else KnowledgeBaseDocumentStatus.QUEUED,
                "file_hash": file_hash,
                "document_info": final_doc.document_info if final_doc else {},
                "parsing_config": final_doc.parsing_config if final_doc else None,
                "chunking_config": final_doc.chunking_config if final_doc else None,
            }

        return doc_data
