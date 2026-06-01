import hashlib
import os
from typing import Annotated
from uuid import UUID

from app.features.knowledge.knowledge_base_documents.facade.pipeline import KnowledgeDocumentPipelineService
from app.features.knowledge.knowledge_base_documents.schemas import (
    KnowledgeBaseDocumentCreate,
    KnowledgeBaseDocumentStatus,
)
from app.features.knowledge.knowledge_base_documents.services import KnowledgeBaseDocumentService
from app.features.knowledge.knowledge_bases.services import KnowledgeBaseService
from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends, HTTPException, UploadFile, status
from loguru import logger
from rag_core.embeddings import resolve_knowledge_embedding_config

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".pdf", ".html", ".htm", ".md", ".docx", ".txt"}


def file_content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class IngestKnowledgeDocumentUseCase(BaseUseCase):
    def __init__(
        self,
        kb_service: Annotated[KnowledgeBaseService, Depends()],
        doc_service: Annotated[KnowledgeBaseDocumentService, Depends()],
        pipeline_service: Annotated[KnowledgeDocumentPipelineService, Depends()],
    ):
        self.kb_service = kb_service
        self.doc_service = doc_service
        self.pipeline_service = pipeline_service

    async def execute(
        self,
        knowledge_base_id: UUID,
        file: UploadFile,
        provider: str | None = None,
    ) -> dict:
        """Validate, parse, chunk, and embed a document into the knowledge base, tracking state transitions and histories."""
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

        # 2. Database record setup (First Transaction: Initialize/Get Document)
        async with AsyncTransaction() as session:
            kb = await self.kb_service.repo.get_by_pk(session, knowledge_base_id)
            if not kb:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Knowledge base with ID '{knowledge_base_id}' not found.",
                )

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
                doc.status = KnowledgeBaseDocumentStatus.READY
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
                    status=KnowledgeBaseDocumentStatus.READY,
                    file_hash=file_hash,
                    document_info={
                        "filename": filename,
                        "size_bytes": len(content),
                        "content_type": file.content_type,
                    },
                )
                doc = await self.doc_service.create(session, doc_create)

            doc_id = doc.id
            kb_name = kb.name
            knowledge_base_id = kb.id
            resolved_parsing_config = (
                doc.parsing_config if doc.parsing_config is not None else kb.default_parsing_config
            )
            resolved_chunking_config = (
                doc.chunking_config if doc.chunking_config is not None else kb.default_chunking_config
            )
            embedding_config = resolve_knowledge_embedding_config(kb.embedding_config)
            previous_embed_config_hash = kb.embed_config_hash

        parsed_doc = await self.pipeline_service.parse_or_load_cached(
            document_id=doc_id,
            knowledge_base_name=kb_name,
            file_hash=file_hash,
            filename=filename,
            content=content,
            content_type=file.content_type,
            parsing_config=resolved_parsing_config,
            provider_override=provider,
        )
        chunks = await self.pipeline_service.rebuild_chunks(
            document_id=doc_id,
            filename=filename,
            parsed_doc=parsed_doc,
            chunking_config=resolved_chunking_config,
            record_history=True,
            history_name_prefix="Chunk",
            failure_detail_prefix="Ingestion",
        )
        await self.pipeline_service.embed_chunks(
            document_id=doc_id,
            filename=filename,
            knowledge_base_id=knowledge_base_id,
            chunks=chunks,
            embedding_config=embedding_config,
            previous_embed_config_hash=previous_embed_config_hash,
            history_name_prefix="Embedding",
            failure_detail_prefix="Ingestion",
        )

        async with AsyncTransaction() as session:
            final_doc = await self.doc_service.repo.get_by_pk(session, doc_id)
            doc_data = {
                "id": str(final_doc.id) if final_doc else str(doc_id),
                "name": final_doc.name if final_doc else filename,
                "status": final_doc.status if final_doc else KnowledgeBaseDocumentStatus.COMPLETED,
                "file_hash": file_hash,
                "document_info": final_doc.document_info if final_doc else {},
                "parsing_config": final_doc.parsing_config if final_doc else None,
                "chunking_config": final_doc.chunking_config if final_doc else None,
            }

        return doc_data
