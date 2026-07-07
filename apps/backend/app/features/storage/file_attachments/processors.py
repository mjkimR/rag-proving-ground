from abc import ABC, abstractmethod
from datetime import timedelta
from uuid import UUID

from app_file_storage import get_storage_client
from app_layer_base.core.database.transaction import AsyncTransaction
from loguru import logger
from rag_core.embeddings import resolve_knowledge_embedding_config
from sqlalchemy import select

from app.common.utils.time_util import get_current_time
from app.features.knowledge.knowledge_base_documents.facade.factory import build_pipeline_service
from app.features.knowledge.knowledge_base_documents.facade.pipeline import (
    PipelineStageContext,
    knowledge_original_file_key,
)
from app.features.knowledge.knowledge_base_documents.models import KnowledgeBaseDocument
from app.features.knowledge.knowledge_bases.models import KnowledgeBase
from app.features.knowledge.session_knowledge_bases.models import SessionKnowledgeBase
from app.features.storage.session_file_attachments.models import SessionFileAttachment


class FileAttachmentProcessor(ABC):
    """Abstract base class for all file attachment processors."""

    @abstractmethod
    async def process(
        self,
        session_file_attachment_id: UUID,
        raw_file_bytes: bytes,
        filename: str,
        mime_type: str,
        sha256: str,
    ) -> dict:
        """Process raw file content and return processing metadata."""
        pass


class TempKbDocumentProcessor(FileAttachmentProcessor):
    """Processor for text documents (PDF, TXT, etc.) to index them into temporary knowledge bases."""

    async def process(
        self,
        session_file_attachment_id: UUID,
        raw_file_bytes: bytes,
        filename: str,
        mime_type: str,
        sha256: str,
    ) -> dict:
        logger.info(f"TempKbDocumentProcessor starting for SessionFileAttachment {session_file_attachment_id}")

        # 1. Fetch the thread_id
        async with AsyncTransaction() as session:
            session_file = await session.get(SessionFileAttachment, session_file_attachment_id)
            if not session_file:
                raise ValueError(f"SessionFileAttachment {session_file_attachment_id} not found.")
            thread_id = session_file.thread_id

        # 2. Check or create temporary KnowledgeBase
        async with AsyncTransaction() as session:
            stmt = select(SessionKnowledgeBase).where(SessionKnowledgeBase.thread_id == thread_id)
            result = await session.execute(stmt)
            session_kb = result.scalars().first()

            if session_kb:
                kb_id = session_kb.knowledge_base_id
                kb = await session.get(KnowledgeBase, kb_id)
                if kb:
                    # Update heartbeat/expiration
                    kb.expires_at = get_current_time() + timedelta(hours=2)
                    logger.info(f"Reusing temporary KB {kb_id} for thread {thread_id}, updated expires_at.")
            else:
                # Create a new temporary KB
                new_kb = KnowledgeBase(
                    name=f"temp_{thread_id}",
                    status="READY",
                    is_temp=True,
                    expires_at=get_current_time() + timedelta(hours=2),
                )
                session.add(new_kb)
                await session.flush()
                kb_id = new_kb.id

                # Link thread to KB
                session_kb = SessionKnowledgeBase(
                    thread_id=thread_id,
                    knowledge_base_id=kb_id,
                )
                session.add(session_kb)
                logger.info(f"Created temporary KB {kb_id} and mapped to thread {thread_id}.")

            await session.flush()

        # 3. Copy raw file to knowledge base storage path
        storage_client = get_storage_client()
        original_file_key = knowledge_original_file_key(kb_id, sha256, filename)
        logger.info(f"Saving copy of file to KB storage key: {original_file_key}")
        await storage_client.upload_file(original_file_key, raw_file_bytes)

        # 4. Check or create KnowledgeBaseDocument
        async with AsyncTransaction() as session:
            existing_docs = await session.execute(
                select(KnowledgeBaseDocument).where(
                    KnowledgeBaseDocument.knowledge_base_id == kb_id,
                    KnowledgeBaseDocument.file_hash == sha256,
                )
            )
            doc = existing_docs.scalars().first()

            if doc:
                doc_id = doc.id
                doc.status = "PROCESSING"
                logger.info(f"Reusing existing KB document {doc_id} with file hash {sha256}.")
            else:
                # Create document record
                doc = KnowledgeBaseDocument(
                    name=filename,
                    knowledge_base_id=kb_id,
                    status="PROCESSING",
                    priority="low",
                    file_hash=sha256,
                    document_info={
                        "filename": filename,
                        "size_bytes": len(raw_file_bytes),
                        "content_type": mime_type,
                        "original_file_path": original_file_key,
                    },
                )
                session.add(doc)
                await session.flush()
                doc_id = doc.id
                logger.info(f"Created new KB document {doc_id} under temporary KB {kb_id}.")

            # Load default configs from KB
            kb = await session.get(KnowledgeBase, kb_id)
            default_parsing_config = kb.default_parsing_config if kb else None
            default_chunking_config = kb.default_chunking_config if kb else None
            embedding_config_raw = kb.embedding_config if kb else None
            previous_embed_config_hash = kb.embed_config_hash if kb else None
            kb_language = kb.language if kb else "en"

            resolved_parsing_config = doc.parsing_config if doc.parsing_config is not None else default_parsing_config
            resolved_chunking_config = (
                doc.chunking_config if doc.chunking_config is not None else default_chunking_config
            )
            embedding_config = resolve_knowledge_embedding_config(embedding_config_raw, language=kb_language)

        # 5. Execute RAG Ingestion Pipeline synchronously
        pipeline_service = build_pipeline_service()

        # Step A: Parse
        logger.info(f"Running sequential pipeline for doc {doc_id}: parsing...")
        parsed_doc = await pipeline_service.parse_or_load_cached(
            document_id=doc_id,
            knowledge_base_id=kb_id,
            file_hash=sha256,
            filename=filename,
            content=raw_file_bytes,
            content_type=mime_type,
            parsing_config=resolved_parsing_config,
        )

        if embedding_config.use_colpali:
            logger.info("PDF page image rendering required for ColPali. Rendering...")
            await pipeline_service.attach_page_images_for_vision(
                parsed_doc=parsed_doc,
                raw_content=raw_file_bytes,
                document_id=doc_id,
            )

        await pipeline_service.save_document_pages(document_id=doc_id, parsed_doc=parsed_doc)

        # Step B: Chunk
        logger.info(f"Running sequential pipeline for doc {doc_id}: chunking...")
        chunks = await pipeline_service.rebuild_chunks(
            document_id=doc_id,
            filename=filename,
            parsed_doc=parsed_doc,
            chunking_config=resolved_chunking_config,
            embedding_config=embedding_config,
            stage_context=PipelineStageContext(
                name_prefix="Chunk",
                failure_detail_prefix="Ingestion",
                record_history=True,
            ),
        )

        # Step C: Embed
        logger.info(f"Running sequential pipeline for doc {doc_id}: embedding...")
        await pipeline_service.embed_chunks(
            document_id=doc_id,
            filename=filename,
            knowledge_base_id=kb_id,
            chunks=chunks,
            embedding_config=embedding_config,
            previous_embed_config_hash=previous_embed_config_hash,
            stage_context=PipelineStageContext(
                name_prefix="Embedding",
                failure_detail_prefix="Ingestion",
            ),
        )

        logger.info(f"TempKbDocumentProcessor successfully ingested doc {doc_id} for KB {kb_id}")
        return {
            "knowledge_base_id": str(kb_id),
            "doc_id": str(doc_id),
            "chunk_count": len(chunks),
        }


class ImageVisionProcessor(FileAttachmentProcessor):
    """Placeholder processor for images (PNG, JPEG, WEBP, etc.)."""

    async def process(
        self,
        session_file_attachment_id: UUID,
        raw_file_bytes: bytes,
        filename: str,
        mime_type: str,
        sha256: str,
    ) -> dict:
        logger.warning(f"ImageVisionProcessor executed (mock/placeholder) for file {filename}")
        return {
            "status": "warning",
            "message": "Image processing is not implemented yet. Raw image preserved.",
            "dimensions": {"width": None, "height": None},
            "processed_storage_path": f"raw-attachments/{sha256}",
        }


class AudioTranscriptionProcessor(FileAttachmentProcessor):
    """Placeholder processor for audio documents (MP3, WAV, etc.)."""

    async def process(
        self,
        session_file_attachment_id: UUID,
        raw_file_bytes: bytes,
        filename: str,
        mime_type: str,
        sha256: str,
    ) -> dict:
        logger.warning(f"AudioTranscriptionProcessor executed (mock/placeholder) for file {filename}")
        return {
            "status": "warning",
            "message": "Audio transcription is not implemented yet. Raw audio preserved.",
            "duration_seconds": None,
            "transcription_text_path": None,
        }
