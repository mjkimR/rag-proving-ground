import hashlib
import json
import os
import time
from typing import Annotated
from uuid import UUID

from app.features.knowledge.knowledge_base_documents.schemas import (
    KnowledgeBaseDocumentCreate,
)
from app.features.knowledge.knowledge_base_documents.services import KnowledgeBaseDocumentService
from app.features.knowledge.knowledge_bases.services import KnowledgeBaseService
from app.features.knowledge.knowledge_chunking_histories.schemas import KnowledgeChunkingHistoryCreate
from app.features.knowledge.knowledge_chunking_histories.services import KnowledgeChunkingHistoryService
from app.features.knowledge.knowledge_embedding_histories.schemas import KnowledgeEmbeddingHistoryCreate
from app.features.knowledge.knowledge_embedding_histories.services import KnowledgeEmbeddingHistoryService
from app.features.knowledge.knowledge_parsing_histories.schemas import KnowledgeParsingHistoryCreate
from app.features.knowledge.knowledge_parsing_histories.services import KnowledgeParsingHistoryService
from app_file_storage import get_storage_client
from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends, HTTPException, UploadFile, status
from loguru import logger
from qdrant_client.http import models as qmodels
from rag_core.adapters.parser.instance import parse_file
from rag_core.adapters.vector_store import check_vector_store_health
from rag_core.adapters.vector_store.instance import get_vector_store, get_vector_store_provider
from rag_core.chunkers import chunk_document
from rag_core.chunkers.schemas import ChunkingConfig
from rag_core.config import get_litellm_settings

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".pdf", ".html", ".htm", ".md", ".docx", ".txt"}


class IngestKnowledgeDocumentUseCase(BaseUseCase):
    def __init__(
        self,
        kb_service: Annotated[KnowledgeBaseService, Depends()],
        doc_service: Annotated[KnowledgeBaseDocumentService, Depends()],
        parse_history_service: Annotated[KnowledgeParsingHistoryService, Depends()],
        chunk_history_service: Annotated[KnowledgeChunkingHistoryService, Depends()],
        embed_history_service: Annotated[KnowledgeEmbeddingHistoryService, Depends()],
    ):
        self.kb_service = kb_service
        self.doc_service = doc_service
        self.parse_history_service = parse_history_service
        self.chunk_history_service = chunk_history_service
        self.embed_history_service = embed_history_service

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

        file_md5 = hashlib.md5(content).hexdigest()

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
                    self.doc_service.repo.model.file_md5 == file_md5,
                ),
            )

            if existing_docs:
                doc = existing_docs[0]
                doc.status = "READY"
                doc.name = filename
                # Update document_info
                doc.document_info = {
                    "filename": filename,
                    "size_bytes": len(content),
                    "content_type": file.content_type,
                }
                await session.flush()
            else:
                doc_create = KnowledgeBaseDocumentCreate(
                    name=filename,
                    knowledge_base_id=knowledge_base_id,
                    status="READY",
                    file_md5=file_md5,
                    document_info={
                        "filename": filename,
                        "size_bytes": len(content),
                        "content_type": file.content_type,
                    },
                )
                doc = await self.doc_service.create(session, doc_create)

            doc_id = doc.id
            kb_name = kb.name
            resolved_parsing_config = doc.parsing_config or kb.default_parsing_config
            resolved_chunking_config = doc.chunking_config or kb.default_chunking_config
            embedding_config = kb.embedding_config or {}

        # 3. Phase 1: Parsing
        async with AsyncTransaction() as session:
            await self.doc_service.repo.update_by_pk(session, doc_id, {"status": "PARSING"})

        parsing_provider = provider or (resolved_parsing_config.get("provider") if resolved_parsing_config else None)
        logger.info(f"Ingest Phase 1: Parsing document '{filename}' (ID: {doc_id}) using provider: {parsing_provider}")

        start_time = time.time()
        try:
            parsed_doc = await parse_file(
                content=content,
                filename=filename,
                content_type=file.content_type,
                provider=parsing_provider,
            )
            duration = time.time() - start_time

            # S3 uploads
            storage_client = get_storage_client()
            base_path = f"knowledge/{kb_name}/{file_md5}"
            original_file_key = f"{base_path}/{filename}"
            parsed_data_key = f"{base_path}/parsed_data.json"

            await storage_client.upload_file(original_file_key, content)
            await storage_client.upload_file(parsed_data_key, parsed_doc.model_dump_json(indent=2).encode("utf-8"))

            async with AsyncTransaction() as session:
                # Update doc_info with file paths and element count
                db_doc = await self.doc_service.repo.get_by_pk(session, doc_id)
                if db_doc:
                    doc_info = dict(db_doc.document_info or {})
                    doc_info.update(
                        {
                            "original_file_path": original_file_key,
                            "parsed_data_path": parsed_data_key,
                            "element_count": len(parsed_doc.elements),
                        }
                    )
                    db_doc.document_info = doc_info

                parse_history = KnowledgeParsingHistoryCreate(
                    name=f"Parse success: {filename}",
                    document_id=doc_id,
                    provider=parsing_provider,
                    status="SUCCESS",
                    parsing_config=resolved_parsing_config,
                    error_message=None,
                    duration_seconds=duration,
                )
                await self.parse_history_service.create(session, parse_history)
                await self.doc_service.repo.update_by_pk(session, doc_id, {"status": "CHUNKING"})

        except Exception as e:
            duration = time.time() - start_time
            logger.exception(f"Parsing failed for document '{filename}': {e}")
            async with AsyncTransaction() as session:
                parse_history = KnowledgeParsingHistoryCreate(
                    name=f"Parse failure: {filename}",
                    document_id=doc_id,
                    provider=parsing_provider,
                    status="FAILED",
                    parsing_config=resolved_parsing_config,
                    error_message=str(e),
                    duration_seconds=duration,
                )
                await self.parse_history_service.create(session, parse_history)
                await self.doc_service.repo.update_by_pk(session, doc_id, {"status": "FAILED"})
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ingestion failed at Parsing stage: {e}",
            ) from e

        # 4. Phase 2: Chunking
        logger.info(f"Ingest Phase 2: Chunking document '{filename}' (ID: {doc_id})")
        start_time = time.time()
        try:
            chunk_config = ChunkingConfig(**resolved_chunking_config) if resolved_chunking_config else ChunkingConfig()
            chunks = chunk_document(parsed_doc, config=chunk_config)
            duration = time.time() - start_time

            async with AsyncTransaction() as session:
                # Update chunk count
                db_doc = await self.doc_service.repo.get_by_pk(session, doc_id)
                if db_doc:
                    doc_info = dict(db_doc.document_info or {})
                    doc_info["chunk_count"] = len(chunks)
                    db_doc.document_info = doc_info

                chunk_history = KnowledgeChunkingHistoryCreate(
                    name=f"Chunk success: {filename}",
                    document_id=doc_id,
                    strategy="semantic",
                    chunk_count=len(chunks),
                    status="SUCCESS",
                    chunking_config=resolved_chunking_config,
                    error_message=None,
                    duration_seconds=duration,
                )
                await self.chunk_history_service.create(session, chunk_history)
                await self.doc_service.repo.update_by_pk(session, doc_id, {"status": "EMBEDDING"})

        except Exception as e:
            duration = time.time() - start_time
            logger.exception(f"Chunking failed for document '{filename}': {e}")
            async with AsyncTransaction() as session:
                chunk_history = KnowledgeChunkingHistoryCreate(
                    name=f"Chunk failure: {filename}",
                    document_id=doc_id,
                    strategy="semantic",
                    chunk_count=0,
                    status="FAILED",
                    chunking_config=resolved_chunking_config,
                    error_message=str(e),
                    duration_seconds=duration,
                )
                await self.chunk_history_service.create(session, chunk_history)
                await self.doc_service.repo.update_by_pk(session, doc_id, {"status": "FAILED"})
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ingestion failed at Chunking stage: {e}",
            ) from e

        # 5. Phase 3: Embedding & Indexing
        logger.info(f"Ingest Phase 3: Embedding & Indexing document '{filename}' (ID: {doc_id})")
        start_time = time.time()
        embedding_model_name = embedding_config.get("model") or get_litellm_settings().default_embedding_model

        try:
            # Check vector store health
            vector_store_healthy = await check_vector_store_health()
            if not vector_store_healthy:
                raise RuntimeError("Vector Database is not healthy or uninitialized.")

            # Calculate hash signature if not set
            async with AsyncTransaction() as session:
                db_kb = await self.kb_service.repo.get_by_pk(session, knowledge_base_id)
                if db_kb and not db_kb.embed_config_hash:
                    config_str = json.dumps({"model": embedding_model_name}, sort_keys=True)
                    embed_config_hash = hashlib.sha256(config_str.encode("utf-8")).hexdigest()[:16]
                    db_kb.embed_config_hash = embed_config_hash
                else:
                    embed_config_hash = db_kb.embed_config_hash if db_kb else "default"

            collection_name = f"vector_store_{embed_config_hash}"
            vector_store = await get_vector_store(collection_name=collection_name, model_name=embedding_model_name)

            # Before adding new points, delete existing points for this doc_id to avoid duplication
            try:
                provider_client = get_vector_store_provider().client
                provider_client.delete(
                    collection_name=collection_name,
                    points_selector=qmodels.FilterSelector(
                        filter=qmodels.Filter(
                            must=[
                                qmodels.FieldCondition(
                                    key="metadata.doc_id",
                                    match=qmodels.MatchValue(value=str(doc_id)),
                                )
                            ]
                        )
                    ),
                )
            except Exception as delete_exc:
                logger.warning(f"Failed to clear old vector store points for doc_id {doc_id}: {delete_exc}")

            lc_docs = []
            for chunk in chunks:
                lc_doc = chunk.to_langchain_document()
                lc_doc.metadata["knowledge_id"] = str(knowledge_base_id)
                lc_docs.append(lc_doc)

            if lc_docs:
                await vector_store.aadd_documents(lc_docs)

            duration = time.time() - start_time

            async with AsyncTransaction() as session:
                embed_history = KnowledgeEmbeddingHistoryCreate(
                    name=f"Embedding success: {filename}",
                    document_id=doc_id,
                    model_name=embedding_model_name,
                    vector_count=len(lc_docs),
                    status="SUCCESS",
                    embedding_config=embedding_config,
                    error_message=None,
                    duration_seconds=duration,
                )
                await self.embed_history_service.create(session, embed_history)
                await self.doc_service.repo.update_by_pk(session, doc_id, {"status": "COMPLETED"})

        except Exception as e:
            duration = time.time() - start_time
            logger.exception(f"Embedding failed for document '{filename}': {e}")
            async with AsyncTransaction() as session:
                embed_history = KnowledgeEmbeddingHistoryCreate(
                    name=f"Embedding failure: {filename}",
                    document_id=doc_id,
                    model_name=embedding_model_name,
                    vector_count=0,
                    status="FAILED",
                    embedding_config=embedding_config,
                    error_message=str(e),
                    duration_seconds=duration,
                )
                await self.embed_history_service.create(session, embed_history)
                await self.doc_service.repo.update_by_pk(session, doc_id, {"status": "FAILED"})
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ingestion failed at Embedding stage: {e}",
            ) from e

        # Get final document record
        async with AsyncTransaction() as session:
            final_doc = await self.doc_service.repo.get_by_pk(session, doc_id)
            doc_data = {
                "id": str(final_doc.id) if final_doc else str(doc_id),
                "name": final_doc.name if final_doc else filename,
                "status": final_doc.status if final_doc else "COMPLETED",
                "file_md5": file_md5,
                "document_info": final_doc.document_info if final_doc else {},
            }

        return doc_data
