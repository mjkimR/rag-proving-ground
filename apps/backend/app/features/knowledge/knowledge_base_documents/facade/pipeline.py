"""Shared document processing phases for knowledge document workflows."""

import json
import time
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
from rag_core.chunkers import ChunkedDocument, ChunkingConfig, chunk_document
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
        knowledge_base_name: str,
        file_hash: str,
        filename: str,
        content: bytes,
        content_type: str | None,
        parsing_config: dict | KnowledgeParsingConfig | None,
        provider_override: str | None = None,
    ) -> ParsedDocument:
        resolved_config = resolve_knowledge_parsing_config(parsing_config, provider_override=provider_override)
        parsing_config_hash = knowledge_parsing_config_hash(resolved_config)
        parsing_provider = resolved_config.provider

        async with AsyncTransaction() as session:
            db_doc = await self.doc_service.repo.get_by_pk(session, document_id)
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
        original_file_key = knowledge_original_file_key(knowledge_base_name, file_hash, filename)
        parsed_data_key = knowledge_parsed_data_key(knowledge_base_name, file_hash)
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
        record_history: bool = True,
        history_name_prefix: str = "Chunk",
        failure_detail_prefix: str = "Ingestion",
    ) -> list[ChunkedDocument]:
        resolved_config = resolve_chunking_config(chunking_config)

        async with AsyncTransaction() as session:
            await self._set_document_status(session, document_id, KnowledgeBaseDocumentStatus.CHUNKING)

        logger.info(f"Chunking document '{filename}' (ID: {document_id})")
        start_time = time.time()
        try:
            from rag_core.embeddings import is_colpali_model

            if embedding_config and is_colpali_model(embedding_config.model):
                from rag_core.chunkers.visual import visual_chunk_document

                chunks = visual_chunk_document(parsed_doc)
            else:
                chunks = chunk_document(parsed_doc, config=resolved_config)

            duration = time.time() - start_time

            async with AsyncTransaction() as session:
                db_doc = await self.doc_service.repo.get_by_pk(session, document_id)
                if db_doc:
                    doc_info = dict(db_doc.document_info or {})
                    doc_info["chunk_count"] = len(chunks)
                    db_doc.document_info = doc_info
                if record_history:
                    chunk_history = JobProcessHistoryCreate(
                        name=f"{history_name_prefix} success: {filename}",
                        resource_type=KNOWLEDGE_DOCUMENT_RESOURCE_TYPE,
                        resource_id=document_id,
                        stage="chunking",
                        outcome="SUCCESS",
                        config=_history_config(resolved_config),
                        metrics={"chunk_count": len(chunks)},
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
                    name=f"{history_name_prefix} failure: {filename}",
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
                detail=f"{failure_detail_prefix} failed at Chunking stage: {exc}",
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
        history_name_prefix: str = "Embedding",
        failure_detail_prefix: str = "Ingestion",
    ) -> None:
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
                    name=f"{history_name_prefix} success: {filename}",
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
                    name=f"{history_name_prefix} failure: {filename}",
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
                detail=f"{failure_detail_prefix} failed at Embedding stage: {exc}",
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
            db_doc = await self.doc_service.repo.get_by_pk(session, document_id)
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
        await self.doc_service.repo.update_by_pk(session, document_id, {"status": document_status})
        await refresh_knowledge_base_status_for_document(session, self.kb_service, self.doc_service, document_id)


def resolve_chunking_config(config: dict | ChunkingConfig | None) -> ChunkingConfig:
    if isinstance(config, ChunkingConfig):
        return config
    if config is None:
        return ChunkingConfig()
    return ChunkingConfig.model_validate(config)


def _history_config(config: BaseModel | dict | None) -> dict | None:
    if config is None:
        return None
    if isinstance(config, BaseModel):
        return config.model_dump(mode="json")
    return dict(config)


def knowledge_original_file_key(knowledge_base_name: str, file_hash: str, filename: str) -> str:
    return f"knowledge/{knowledge_base_name}/{file_hash}/{filename}"


def knowledge_parsed_data_key(knowledge_base_name: str, file_hash: str) -> str:
    return f"knowledge/{knowledge_base_name}/{file_hash}/parsed_data.json"


async def load_parsed_document_from_storage(parsed_data_path: str) -> ParsedDocument:
    storage_client = get_storage_client()
    if not await storage_client.file_exists(parsed_data_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parsed document data not found in storage.",
        )
    data = await storage_client.download_file(parsed_data_path)
    return ParsedDocument(**json.loads(data.decode("utf-8")))
