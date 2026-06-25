import hashlib
import json
import time
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from app.features.history.job_process_histories.schemas import JobProcessHistoryCreate
from app.features.history.job_process_histories.services import JobProcessHistoryService
from app.features.knowledge.knowledge_base_documents.schemas import KnowledgeBaseDocumentStatus
from app.features.knowledge.knowledge_base_documents.services import KnowledgeBaseDocumentService
from app.features.knowledge.knowledge_base_pages.services import KnowledgeBasePageService
from app.features.knowledge.knowledge_bases.services import KnowledgeBaseService
from app.features.knowledge.knowledge_bases.status import refresh_knowledge_base_status_for_document
from app_file_storage import get_storage_client
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel
from rag_core.adapters.parser.instance import parse_file
from rag_core.chunkers import (
    ChunkedDocument,
    ChunkingConfig,
    chunk_document,
    knowledge_chunking_config_hash,
    resolve_chunking_config,
)
from rag_core.embeddings import (
    KnowledgeEmbeddingConfig,
    chunks_to_langchain_documents,
    delete_document_vectors,
    get_knowledge_vector_store,
    knowledge_vector_collection_name,
)
from rag_core.parsers import (
    KnowledgeParsingConfig,
    ParsedDocument,
    knowledge_parsing_config_hash,
    resolve_knowledge_parsing_config,
)
from sqlalchemy.ext.asyncio import AsyncSession

KNOWLEDGE_DOCUMENT_RESOURCE_TYPE = "knowledge_base_document"


@dataclass(frozen=True)
class PipelineStageContext:
    name_prefix: str
    failure_detail_prefix: str = "Ingestion"
    record_history: bool = True


class KnowledgeDocumentPipelineService:
    def __init__(
        self,
        kb_service: Annotated[KnowledgeBaseService, Depends()],
        doc_service: Annotated[KnowledgeBaseDocumentService, Depends()],
        history_service: Annotated[JobProcessHistoryService, Depends()],
        page_service: Annotated[KnowledgeBasePageService, Depends()],
    ) -> None:
        self.kb_service = kb_service
        self.doc_service = doc_service
        self.history_service = history_service
        self.page_service = page_service

    async def parse_or_load_cached(
        self,
        *,
        document_id: UUID,
        knowledge_base_id: UUID,
        file_hash: str,
        filename: str,
        content: bytes,
        content_type: str | None,
        parsing_config: dict | KnowledgeParsingConfig | None,
        provider_override: str | None = None,
    ) -> ParsedDocument:
        resolved_config = resolve_knowledge_parsing_config(parsing_config, provider_override=provider_override)
        parsing_config_hash = knowledge_parsing_config_hash(resolved_config)
        parsing_provider = provider_override or resolved_config.get_provider_for_filename(filename)

        async with AsyncTransaction() as session:
            db_doc = await self.doc_service.repo.get_by_pk_for_update(session, document_id)
            if db_doc:
                doc_info = dict(db_doc.document_info or {})
                db_parsing_config_hash = doc_info.get("parsing_config_hash")
            else:
                db_parsing_config_hash = None

            await self._set_document_status(session, document_id, KnowledgeBaseDocumentStatus.PARSING)

        logger.info(
            f"Ingest Phase 1: Parsing document '{filename}' (ID: {document_id}) using provider: {parsing_provider}"
        )

        storage_client = get_storage_client()
        original_file_key = knowledge_original_file_key(knowledge_base_id, file_hash, filename)
        parsed_data_key = knowledge_parsed_data_key(knowledge_base_id, file_hash)
        start_time = time.time()

        try:
            if db_parsing_config_hash == parsing_config_hash and await storage_client.file_exists(parsed_data_key):
                parsed_doc = await load_parsed_document_from_storage(parsed_data_key)
                await storage_client.upload_file(original_file_key, content)
                duration = time.time() - start_time
                await self._record_parse_success(
                    document_id=document_id,
                    filename=filename,
                    provider=parsing_provider,
                    parsing_config=resolved_config,
                    duration=duration,
                    parsed_doc=parsed_doc,
                    original_file_key=original_file_key,
                    parsed_data_key=parsed_data_key,
                    parsing_config_hash=parsing_config_hash,
                    cache_hit=True,
                )
                return parsed_doc

            parsed_doc = await parse_file(
                content=content,
                filename=filename,
                content_type=content_type,
                provider=parsing_provider,
                parsing_config_hash=parsing_config_hash,
            )
            cache_hit = False
            if hasattr(parsed_doc, "metadata") and isinstance(parsed_doc.metadata, dict):
                cache_hit = parsed_doc.metadata.get("cache_hit", False)

            await storage_client.upload_file(original_file_key, content)
            await storage_client.upload_file(parsed_data_key, parsed_doc.model_dump_json(indent=2).encode("utf-8"))
            duration = time.time() - start_time
            await self._record_parse_success(
                document_id=document_id,
                filename=filename,
                provider=parsing_provider,
                parsing_config=resolved_config,
                duration=duration,
                parsed_doc=parsed_doc,
                original_file_key=original_file_key,
                parsed_data_key=parsed_data_key,
                parsing_config_hash=parsing_config_hash,
                cache_hit=cache_hit,
            )
            return parsed_doc
        except HTTPException:
            raise
        except Exception as exc:
            duration = time.time() - start_time
            logger.exception(f"Parsing failed for document '{filename}': {exc}")
            async with AsyncTransaction() as session:
                parse_history = JobProcessHistoryCreate(
                    name=f"Parse failure: {filename}",
                    resource_type=KNOWLEDGE_DOCUMENT_RESOURCE_TYPE,
                    resource_id=document_id,
                    stage="parsing",
                    outcome="FAILED",
                    provider=parsing_provider,
                    config=_history_config(resolved_config),
                    metrics=None,
                    error_message=str(exc),
                    duration_seconds=duration,
                )
                await self.history_service.record(session, parse_history)
                await self._set_document_status(session, document_id, KnowledgeBaseDocumentStatus.FAILED)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ingestion failed at Parsing stage: {exc}",
            ) from exc

    async def rebuild_chunks(
        self,
        *,
        document_id: UUID,
        filename: str,
        parsed_doc: ParsedDocument,
        chunking_config: dict | ChunkingConfig | None,
        embedding_config: KnowledgeEmbeddingConfig | None = None,
        stage_context: PipelineStageContext | None = None,
    ) -> list[ChunkedDocument]:
        if stage_context is None:
            stage_context = PipelineStageContext(name_prefix="Chunk")
        resolved_config = resolve_chunking_config(chunking_config)
        chunking_config_hash = knowledge_chunking_config_hash(resolved_config)

        # Explicitly declare scope variables to improve readability and satisfy linters
        doc_info: dict = {}
        db_chunk_hash: str | None = None
        db_summary_hash: str | None = None

        async with AsyncTransaction() as session:
            await self._set_document_status(session, document_id, KnowledgeBaseDocumentStatus.CHUNKING)
            db_doc = await self.doc_service.repo.get_by_pk_for_update(session, document_id)
            if not db_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document with ID '{document_id}' not found.",
                )
            kb_id = db_doc.knowledge_base_id
            file_hash = db_doc.file_hash
            doc_info = dict(db_doc.document_info or {})
            db_chunk_hash = doc_info.get("chunking_config_hash")
            db_summary_hash = doc_info.get("chunking_summary_hash")

        logger.info(f"Chunking document '{filename}' (ID: {document_id})")
        start_time = time.time()
        storage_client = get_storage_client()
        chunked_data_key = knowledge_chunked_data_key(kb_id, file_hash)

        try:
            # Generate summary if Contextual Retrieval is enabled
            summary_to_prepend = None
            if resolved_config.enable_contextual_retrieval:
                # 1. Fetch DB doc without locking the row, to see if summary already exists
                async with AsyncTransaction() as session:
                    db_doc_check = await self.doc_service.repo.get_by_pk(session, document_id)
                    db_summary = db_doc_check.summary if db_doc_check else None
                    needs_summary = db_doc_check and db_summary is None

                if needs_summary:
                    logger.info(f"Generating contextual retrieval summary for document '{filename}'")
                    from rag_core.summarize import TreeSummarizer

                    summarizer = TreeSummarizer(model_name=resolved_config.contextual_retrieval_model)

                    elements = parsed_doc.elements
                    full_text_chunks = []
                    for page in parsed_doc.pages:
                        page_text = "\n\n".join(
                            e.content
                            for e in elements
                            if e.page_id == page.page_id and e.content.strip() and not e.ignored
                        )
                        if page_text:
                            full_text_chunks.append(page_text)

                    # If elements not linked by page_id (or fallback), just get all text
                    if not full_text_chunks:
                        full_text_chunks = [
                            e.content
                            for e in elements
                            if e.content.strip() and not e.ignored
                        ]

                    full_text = "\n\n".join(full_text_chunks)
                    if full_text.strip():
                        summary_query = (
                            "Please provide a comprehensive summary of this document. "
                            "This summary will be used to provide context for smaller chunks of the document during retrieval. "
                            "Focus on the main topics, entities, and overall context of the document."
                        )
                        # Perform long running LLM generation outside of DB lock
                        summary = await summarizer.summarize(full_text, query=summary_query)

                        # 2. Re-fetch with lock to save summary (Double-Checked Locking)
                        was_generated = False
                        async with AsyncTransaction() as session:
                            db_doc_for_summary = await self.doc_service.repo.get_by_pk_for_update(session, document_id)
                            if db_doc_for_summary:
                                if db_doc_for_summary.summary is None:
                                    db_doc_for_summary.summary = summary
                                    db_doc_for_summary.summary_model = summarizer.model_name
                                    await session.flush()
                                    summary_to_prepend = summary
                                    was_generated = True
                                else:
                                    summary_to_prepend = db_doc_for_summary.summary

                        if was_generated:
                            logger.info(
                                f"Saved summary for document '{filename}' using model {summarizer.model_name}"
                            )
                        else:
                            logger.info(
                                f"Summary for document '{filename}' was already generated by another worker. Using existing summary."
                            )
                    else:
                        summary_to_prepend = None
                else:
                    summary_to_prepend = db_summary

            # Compute summary hash for cache mapping
            current_summary_hash = (
                hashlib.sha256(summary_to_prepend.encode("utf-8")).hexdigest()[:16]
                if summary_to_prepend
                else None
            )

            # 1. Check if cache is valid (matching hash, summary hash, and file exists in MinIO)
            if (
                db_chunk_hash == chunking_config_hash
                and db_summary_hash == current_summary_hash
                and await storage_client.file_exists(chunked_data_key)
            ):
                logger.info(f"Chunk cache hit for document '{filename}' (ID: {document_id})")
                chunks = await load_chunked_document_from_storage(chunked_data_key)
                duration = time.time() - start_time

                async with AsyncTransaction() as session:
                    if stage_context.record_history:
                        chunk_history = JobProcessHistoryCreate(
                            name=f"{stage_context.name_prefix} cache hit: {filename}",
                            resource_type=KNOWLEDGE_DOCUMENT_RESOURCE_TYPE,
                            resource_id=document_id,
                            stage="chunking",
                            outcome="SUCCESS",
                            config=_history_config(resolved_config),
                            metrics={"chunk_count": len(chunks), "cache_hit": True},
                            error_message=None,
                            duration_seconds=duration,
                        )
                        await self.history_service.record(session, chunk_history)
                    await self._set_document_status(session, document_id, KnowledgeBaseDocumentStatus.EMBEDDING)
                return chunks

            # 2. Cache miss: perform the actual chunking
            logger.info(f"Chunk cache miss for document '{filename}' (ID: {document_id})")

            if embedding_config and embedding_config.use_colpali:
                from rag_core.chunkers.visual import visual_chunk_document

                chunks = visual_chunk_document(parsed_doc)
            else:
                chunks = chunk_document(parsed_doc, config=resolved_config, summary=summary_to_prepend) # type: ignore

            # 3. Save chunking results to MinIO
            serialized_chunks = json.dumps([c.model_dump() for c in chunks], indent=2).encode("utf-8")
            await storage_client.upload_file(chunked_data_key, serialized_chunks)

            duration = time.time() - start_time

            async with AsyncTransaction() as session:
                db_doc = await self.doc_service.repo.get_by_pk_for_update(session, document_id)
                if db_doc:
                    doc_info = dict(db_doc.document_info or {})
                    doc_info["chunk_count"] = len(chunks)
                    doc_info["chunking_config_hash"] = chunking_config_hash
                    doc_info["chunking_summary_hash"] = current_summary_hash
                    doc_info["chunked_data_path"] = chunked_data_key
                    db_doc.document_info = doc_info
                if stage_context.record_history:
                    chunk_history = JobProcessHistoryCreate(
                        name=f"{stage_context.name_prefix} success: {filename}",
                        resource_type=KNOWLEDGE_DOCUMENT_RESOURCE_TYPE,
                        resource_id=document_id,
                        stage="chunking",
                        outcome="SUCCESS",
                        config=_history_config(resolved_config),
                        metrics={"chunk_count": len(chunks), "cache_hit": False},
                        error_message=None,
                        duration_seconds=duration,
                    )
                    await self.history_service.record(session, chunk_history)
                await self._set_document_status(session, document_id, KnowledgeBaseDocumentStatus.EMBEDDING)
            return chunks
        except Exception as exc:
            duration = time.time() - start_time
            logger.exception(f"Chunking failed for document '{filename}': {exc}")
            async with AsyncTransaction() as session:
                chunk_history = JobProcessHistoryCreate(
                    name=f"{stage_context.name_prefix} failure: {filename}",
                    resource_type=KNOWLEDGE_DOCUMENT_RESOURCE_TYPE,
                    resource_id=document_id,
                    stage="chunking",
                    outcome="FAILED",
                    config=_history_config(resolved_config),
                    metrics={"chunk_count": 0},
                    error_message=str(exc),
                    duration_seconds=duration,
                )
                await self.history_service.record(session, chunk_history)
                await self._set_document_status(session, document_id, KnowledgeBaseDocumentStatus.FAILED)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"{stage_context.failure_detail_prefix} failed at Chunking stage: {exc}",
            ) from exc

    async def embed_chunks(
        self,
        *,
        document_id: UUID,
        filename: str,
        knowledge_base_id: UUID,
        chunks: list[ChunkedDocument],
        embedding_config: KnowledgeEmbeddingConfig,
        previous_embed_config_hash: str | None,
        stage_context: PipelineStageContext | None = None,
    ) -> None:
        if stage_context is None:
            stage_context = PipelineStageContext(name_prefix="Embedding")
        logger.info(f"Embedding & indexing document '{filename}' (ID: {document_id})")
        start_time = time.time()
        embedding_model_name = embedding_config.model or ""
        try:
            vector_store, collection_name, embed_config_hash = await get_knowledge_vector_store(embedding_config)

            async with AsyncTransaction() as session:
                db_kb = await self.kb_service.repo.get_by_pk(session, knowledge_base_id)
                if db_kb:
                    db_kb.embed_config_hash = embed_config_hash

            collection_names_to_clear = {collection_name}
            if previous_embed_config_hash and previous_embed_config_hash != embed_config_hash:
                collection_names_to_clear.add(knowledge_vector_collection_name(previous_embed_config_hash))
            for vector_collection_name in collection_names_to_clear:
                try:
                    await delete_document_vectors(vector_collection_name, document_id)
                except Exception as delete_exc:
                    logger.warning(
                        f"Failed to clear old vector store points for doc_id {document_id} "
                        f"in collection {vector_collection_name}: {delete_exc}"
                    )

            lc_docs = chunks_to_langchain_documents(chunks, knowledge_base_id=knowledge_base_id)
            if lc_docs:
                batch_size = 200
                total_docs = len(lc_docs)
                logger.info(f"Adding {total_docs} documents to vector store in batches of {batch_size}")
                for i in range(0, total_docs, batch_size):
                    batch = lc_docs[i : i + batch_size]
                    logger.debug(
                        f"Inserting batch {i // batch_size + 1}/{(total_docs + batch_size - 1) // batch_size} "
                        f"({len(batch)} documents)"
                    )
                    await vector_store.aadd_documents(batch)
            duration = time.time() - start_time

            async with AsyncTransaction() as session:
                embed_history = JobProcessHistoryCreate(
                    name=f"{stage_context.name_prefix} success: {filename}",
                    resource_type=KNOWLEDGE_DOCUMENT_RESOURCE_TYPE,
                    resource_id=document_id,
                    stage="embedding",
                    outcome="SUCCESS",
                    model_name=embedding_model_name,
                    config=_history_config(embedding_config),
                    metrics={"vector_count": len(lc_docs)},
                    error_message=None,
                    duration_seconds=duration,
                )
                await self.history_service.record(session, embed_history)
                await self._set_document_status(session, document_id, KnowledgeBaseDocumentStatus.COMPLETED)
        except Exception as exc:
            duration = time.time() - start_time
            logger.exception(f"Embedding failed for document '{filename}': {exc}")
            async with AsyncTransaction() as session:
                embed_history = JobProcessHistoryCreate(
                    name=f"{stage_context.name_prefix} failure: {filename}",
                    resource_type=KNOWLEDGE_DOCUMENT_RESOURCE_TYPE,
                    resource_id=document_id,
                    stage="embedding",
                    outcome="FAILED",
                    model_name=embedding_model_name,
                    config=_history_config(embedding_config),
                    metrics={"vector_count": 0},
                    error_message=str(exc),
                    duration_seconds=duration,
                )
                await self.history_service.record(session, embed_history)
                await self._set_document_status(session, document_id, KnowledgeBaseDocumentStatus.FAILED)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"{stage_context.failure_detail_prefix} failed at Embedding stage: {exc}",
            ) from exc

    async def _record_parse_success(
        self,
        *,
        document_id: UUID,
        filename: str,
        provider: str | None,
        parsing_config: KnowledgeParsingConfig,
        duration: float,
        parsed_doc: ParsedDocument,
        original_file_key: str,
        parsed_data_key: str,
        parsing_config_hash: str,
        cache_hit: bool,
    ) -> None:
        async with AsyncTransaction() as session:
            db_doc = await self.doc_service.repo.get_by_pk_for_update(session, document_id)
            if db_doc:
                doc_info = dict(db_doc.document_info or {})
                doc_info.update(
                    {
                        "original_file_path": original_file_key,
                        "parsed_data_path": parsed_data_key,
                        "parsing_config_hash": parsing_config_hash,
                        "element_count": len(parsed_doc.elements),
                    }
                )
                db_doc.document_info = doc_info
            parse_history = JobProcessHistoryCreate(
                name=f"Parse {'cache hit' if cache_hit else 'success'}: {filename}",
                resource_type=KNOWLEDGE_DOCUMENT_RESOURCE_TYPE,
                resource_id=document_id,
                stage="parsing",
                outcome="SUCCESS",
                provider=provider,
                config=_history_config(parsing_config),
                metrics={
                    "element_count": len(parsed_doc.elements),
                    "cache_hit": cache_hit,
                },
                error_message=None,
                duration_seconds=duration,
            )
            await self.history_service.record(session, parse_history)
            await self._set_document_status(session, document_id, KnowledgeBaseDocumentStatus.CHUNKING)

    async def _set_document_status(
        self,
        session: AsyncSession,
        document_id: UUID,
        document_status: KnowledgeBaseDocumentStatus,
    ) -> None:
        db_doc = await self.doc_service.repo.get_by_pk_for_update(session, document_id)
        if db_doc:
            db_doc.status = document_status
            await session.flush()
        await refresh_knowledge_base_status_for_document(session, self.kb_service, self.doc_service, document_id)


def _history_config(config: BaseModel | dict | None) -> dict | None:
    if config is None:
        return None
    if isinstance(config, BaseModel):
        return config.model_dump(mode="json")
    return dict(config)


def knowledge_original_file_key(knowledge_base_id: UUID | str, file_hash: str, filename: str) -> str:
    return f"knowledge/{knowledge_base_id}/{file_hash}/{filename}"


def knowledge_parsed_data_key(knowledge_base_id: UUID | str, file_hash: str) -> str:
    return f"knowledge/{knowledge_base_id}/{file_hash}/parsed_data.json"


def knowledge_chunked_data_key(knowledge_base_id: UUID | str, file_hash: str) -> str:
    return f"knowledge/{knowledge_base_id}/{file_hash}/chunked_data.json"


async def load_parsed_document_from_storage(parsed_data_path: str) -> ParsedDocument:
    storage_client = get_storage_client()
    if not await storage_client.file_exists(parsed_data_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parsed document data not found in storage.",
        )
    data = await storage_client.download_file(parsed_data_path)
    return ParsedDocument(**json.loads(data.decode("utf-8")))


async def load_chunked_document_from_storage(chunked_data_path: str) -> list[ChunkedDocument]:
    storage_client = get_storage_client()
    if not await storage_client.file_exists(chunked_data_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chunked document data not found in storage.",
        )
    data = await storage_client.download_file(chunked_data_path)
    items = json.loads(data.decode("utf-8"))
    return [ChunkedDocument(**item) for item in items]
