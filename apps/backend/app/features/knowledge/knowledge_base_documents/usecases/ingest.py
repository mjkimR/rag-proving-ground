import asyncio
import hashlib
import os
from typing import Annotated
from uuid import UUID

from app.features.knowledge.knowledge_base_documents.facade.pipeline import knowledge_original_file_key
from app.features.knowledge.knowledge_base_documents.schemas import (
    KnowledgeBaseDocumentCreate,
    KnowledgeBaseDocumentStatus,
    TaskPriority,
)
from app.features.knowledge.knowledge_base_documents.services import KnowledgeBaseDocumentService
from app.features.knowledge.knowledge_base_documents.usecases.crud import (
    KnowledgeDocumentCleanupTarget,
    cleanup_knowledge_document_assets,
)
from app.features.knowledge.knowledge_bases.services import KnowledgeBaseService
from app.features.knowledge.knowledge_bases.status import refresh_knowledge_base_status
from app_file_storage import get_storage_client
from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import BackgroundTasks, Depends, HTTPException, UploadFile, status
from loguru import logger

_BACKGROUND_CLEANUP_TASKS: set[asyncio.Task] = set()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".pdf", ".html", ".htm", ".md", ".docx", ".txt"}

STALE_INFO_KEYS = [
    "parsing_config_hash",
    "chunking_config_hash",
    "chunking_summary_hash",
    "chunk_count",
    "original_file_path",
    "parsed_data_path",
    "chunked_data_path",
]


async def run_background_cleanup(target: KnowledgeDocumentCleanupTarget) -> None:
    """Helper to run the asset cleanup process asynchronously with a timeout."""
    try:
        # Set a conservative timeout of 5 minutes (300 seconds) to prevent task leakage
        errors = await asyncio.wait_for(cleanup_knowledge_document_assets(target), timeout=300.0)
        if errors:
            logger.error(
                f"Background cleanup failed for document {target.document_id} (hash: {target.file_hash}): "
                f"{'; '.join(errors)}"
            )
    except TimeoutError:
        logger.error(
            f"Background cleanup timed out for document {target.document_id} (hash: {target.file_hash}) after 300 seconds"
        )
    except Exception as exc:
        logger.exception(f"Unexpected error during background cleanup for document {target.document_id}: {exc}")


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
        priority: TaskPriority = TaskPriority.LOW,
        background_tasks: BackgroundTasks | None = None,
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
        cleanup_targets: list[KnowledgeDocumentCleanupTarget] = []

        # 2. Database record setup (First Transaction: Initialize/Get Document)
        async with AsyncTransaction() as session:
            kb = await self.kb_service.repo.get_by_pk(session, knowledge_base_id)
            if not kb:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Knowledge base with ID '{knowledge_base_id}' not found.",
                )

            # Check if document already exists by filename inside the same knowledge base
            existing_docs = await self.doc_service.repo.get_all(
                session,
                where=(
                    self.doc_service.repo.model.knowledge_base_id == knowledge_base_id,
                    self.doc_service.repo.model.name == filename,
                ),
            )

            if existing_docs:
                doc = existing_docs[0]
                if doc.file_hash == file_hash:
                    # If content hash is the same, do not process again unless it was failed
                    if doc.status == KnowledgeBaseDocumentStatus.FAILED:
                        doc.status = KnowledgeBaseDocumentStatus.QUEUED
                        doc.priority = priority
                        doc.error_message = None
                else:
                    # Content hash has changed -> perform overwrite and invalidate cached stages
                    old_file_hash = doc.file_hash
                    old_cleanup_target = KnowledgeDocumentCleanupTarget(
                        document_id=doc.id,
                        file_hash=old_file_hash,
                        knowledge_base_id=knowledge_base_id,
                        knowledge_base_name=kb.name if kb else "unknown",
                        embed_config_hash=kb.embed_config_hash if kb else None,
                    )
                    cleanup_targets.append(old_cleanup_target)

                    doc.file_hash = file_hash
                    doc.status = KnowledgeBaseDocumentStatus.QUEUED
                    doc.priority = priority
                    doc.error_message = None
                    doc.summary = None
                    doc.summary_model = None

                    doc_info = dict(doc.document_info or {})
                    doc_info.update(
                        {
                            "filename": filename,
                            "size_bytes": len(content),
                            "content_type": file.content_type,
                        }
                    )
                    # Clear stale parser/chunker hashes & cached paths to force reprocessing
                    for key in STALE_INFO_KEYS:
                        doc_info.pop(key, None)
                    doc.document_info = doc_info

                await session.flush()
            else:
                doc_create = KnowledgeBaseDocumentCreate(
                    name=filename,
                    knowledge_base_id=knowledge_base_id,
                    status=KnowledgeBaseDocumentStatus.QUEUED,
                    priority=priority,
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

        # Trigger background cleanups only after the transaction commits successfully
        for target in cleanup_targets:
            if background_tasks:
                background_tasks.add_task(run_background_cleanup, target)
            else:
                task = asyncio.create_task(run_background_cleanup(target))
                _BACKGROUND_CLEANUP_TASKS.add(task)
                task.add_done_callback(_BACKGROUND_CLEANUP_TASKS.discard)

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

        # 4. Return immediate response (Staging dispatcher will pick it up from DB)
        async with AsyncTransaction() as session:
            final_doc = await self.doc_service.repo.get_by_pk(session, doc_id)
            doc_data = {
                "id": str(final_doc.id) if final_doc else str(doc_id),
                "name": final_doc.name if final_doc else filename,
                "status": final_doc.status if final_doc else KnowledgeBaseDocumentStatus.QUEUED,
                "priority": final_doc.priority if final_doc else priority,
                "file_hash": file_hash,
                "document_info": final_doc.document_info if final_doc else {},
                "parsing_config": final_doc.parsing_config if final_doc else None,
                "chunking_config": final_doc.chunking_config if final_doc else None,
            }

        return doc_data
