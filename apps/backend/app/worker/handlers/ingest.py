from app.features.knowledge.knowledge_base_documents.facade.pipeline import (
    PipelineStageContext,
    knowledge_original_file_key,
    load_chunked_document_from_storage,
    load_parsed_document_from_storage,
)
from app.features.knowledge.knowledge_base_documents.models import KnowledgeBaseDocument
from app.features.knowledge.knowledge_base_documents.schemas import (
    ChunkDocumentMessage,
    EmbedDocumentMessage,
    KnowledgeBaseDocumentStatus,
    ParseDocumentMessage,
)
from app.features.knowledge.knowledge_base_pages.schemas import KnowledgeBasePageCreate
from app.features.knowledge.knowledge_bases.status import refresh_knowledge_base_status_for_document
from app.worker.broker import broker
from app.worker.services import build_pipeline_service
from app_file_storage import get_storage_client
from app_layer_base.core.database.transaction import AsyncTransaction
from loguru import logger
from rag_core.embeddings import resolve_knowledge_embedding_config
from sqlalchemy import update
from tenacity import retry, stop_after_attempt


@broker.task(task_name="parse_document")
@retry(stop=stop_after_attempt(3))
async def handle_parse(msg: ParseDocumentMessage) -> None:
    """Process a document parsing stage.

    Retrieves the document and knowledge base from DB, downloads the file from
    MinIO, then runs the parse stage and page generation.
    """
    logger.info(f"Worker received parse message for document {msg.document_id}")

    pipeline_service = build_pipeline_service()

    try:
        # Fetch KB details outside the locked transaction to prevent pool starvation
        async with AsyncTransaction() as session:
            kb = await pipeline_service.kb_service.repo.get_by_pk(session, msg.knowledge_base_id)
            if not kb:
                logger.error(f"Knowledge base with ID '{msg.knowledge_base_id}' not found.")
                return
            default_parsing_config = kb.default_parsing_config
            embedding_config_raw = kb.embedding_config
            kb_language = kb.language if kb else "en"

        # Retrieve document and mark status inside a short locked transaction
        async with AsyncTransaction() as session:
            doc = await pipeline_service.doc_service.repo.get_by_pk_for_update(session, msg.document_id)
            if not doc:
                logger.error(f"Document with ID '{msg.document_id}' not found.")
                return

            if doc.status in (
                KnowledgeBaseDocumentStatus.CHUNKING,
                KnowledgeBaseDocumentStatus.EMBEDDING,
                KnowledgeBaseDocumentStatus.COMPLETED,
            ):
                logger.info(f"Document {msg.document_id} is already in state {doc.status}. Skipping parse stage.")
                return

            # Mark status as PARSING immediately inside lock
            doc.status = KnowledgeBaseDocumentStatus.PARSING
            await session.flush()

            resolved_parsing_config = doc.parsing_config if doc.parsing_config is not None else default_parsing_config
            embedding_config = resolve_knowledge_embedding_config(embedding_config_raw, language=kb_language)

        # 2. Download raw file from MinIO
        storage_client = get_storage_client()
        original_file_key = knowledge_original_file_key(msg.knowledge_base_id, msg.file_hash, msg.filename)
        try:
            content = await storage_client.download_file(original_file_key)
        except Exception as exc:
            logger.error(f"Failed to download file {original_file_key} from storage: {exc}")
            raise exc

        # 3. Run the parser
        logger.info(f"Worker starting parse stage for document {msg.document_id}")
        parsed_doc = await pipeline_service.parse_or_load_cached(
            document_id=msg.document_id,
            knowledge_base_id=msg.knowledge_base_id,
            file_hash=msg.file_hash,
            filename=msg.filename,
            content=content,
            content_type=msg.content_type,
            parsing_config=resolved_parsing_config,
            provider_override=msg.provider,
        )

        is_vision_rag = embedding_config.use_colpali

        if is_vision_rag:
            logger.info(f"ColPali model detected. Rendering pages to images for document {msg.document_id}")
            from rag_core.parsers.pdf_page_renderer import render_and_store_pdf_pages

            asset_refs = await render_and_store_pdf_pages(content, str(msg.document_id), storage_client)
            # Map page images back to parsed_doc.pages
            sorted_pages = sorted(parsed_doc.pages, key=lambda p: p.page_no)
            for page, asset_ref in zip(sorted_pages, asset_refs, strict=True):
                page.image = asset_ref

        logger.info(f"Worker saving pages for document {msg.document_id}")
        # Group and sort elements by page_id in O(N log N)
        from collections import defaultdict

        elements_by_page = defaultdict(list)
        for element in parsed_doc.elements:
            if element.page_id:
                elements_by_page[element.page_id].append(element)
        for page_id in elements_by_page:
            elements_by_page[page_id].sort(key=lambda e: e.order)

        # Batch insert pages (e.g., 50 pages per batch) inside a single transaction to ensure atomicity
        batch_size = 50
        page_creates = []
        async with AsyncTransaction() as session:
            await pipeline_service.page_service.repo.delete_by_document_id(session, msg.document_id)
            for page in parsed_doc.pages:
                page_elements = elements_by_page.get(page.page_id, [])
                content_text = "\n\n".join(e.content for e in page_elements if not e.ignored and e.content.strip())

                metadata_info = dict(page.metadata)
                if page.image:
                    metadata_info["image"] = page.image.model_dump()

                page_creates.append(
                    KnowledgeBasePageCreate(
                        document_id=msg.document_id,
                        page_id=page.page_id,
                        page_number=page.page_no,
                        content=content_text,
                        metadata_info=metadata_info,
                    )
                )
                if len(page_creates) >= batch_size:
                    await pipeline_service.page_service.repo.bulk_create(session, page_creates, msg.document_id)
                    page_creates = []

            if page_creates:
                await pipeline_service.page_service.repo.bulk_create(session, page_creates, msg.document_id)

        # 4. Chain: Dispatch to handle_chunk
        logger.info(f"Worker completed parse stage. Dispatching chunk task for {msg.document_id}")
        from app.features.knowledge.knowledge_base_documents.schemas import get_queue_name, map_priority_to_int

        kicker = handle_chunk.kicker().with_labels(
            queue_name=get_queue_name(msg.priority, stage="chunk"),
            priority=map_priority_to_int(msg.priority),
        )
        await kicker.kiq(
            ChunkDocumentMessage(
                document_id=msg.document_id,
                knowledge_base_id=msg.knowledge_base_id,
                filename=msg.filename,
                priority=msg.priority,
            )
        )

    except Exception as exc:
        logger.error(f"Parse worker execution failed for document {msg.document_id}: {exc}")
        await _update_status_to_failed(pipeline_service, msg.document_id, error_message=str(exc))
        raise exc


@broker.task(task_name="chunk_document")
@retry(stop=stop_after_attempt(3))
async def handle_chunk(msg: ChunkDocumentMessage) -> None:
    """Process a document chunking stage.

    Retrieves the document and knowledge base details from DB, loads parsed
    document from MinIO, then runs the chunker.
    """
    logger.info(f"Worker received chunk message for document {msg.document_id}")

    pipeline_service = build_pipeline_service()

    try:
        # 1. Retrieve document and mark status inside a short locked transaction
        async with AsyncTransaction() as session:
            doc = await pipeline_service.doc_service.repo.get_by_pk_for_update(session, msg.document_id)
            if not doc:
                logger.error(f"Document with ID '{msg.document_id}' not found.")
                return

            if doc.status in (
                KnowledgeBaseDocumentStatus.EMBEDDING,
                KnowledgeBaseDocumentStatus.COMPLETED,
            ):
                logger.info(f"Document {msg.document_id} is already in state {doc.status}. Skipping chunk stage.")
                return

            # Mark status as CHUNKING immediately inside lock
            doc.status = KnowledgeBaseDocumentStatus.CHUNKING
            await session.flush()

            kb_id = doc.knowledge_base_id
            document_info = dict(doc.document_info or {})
            chunking_config_override = doc.chunking_config

        # 2. Retrieve knowledge base details outside the lock to prevent pool starvation
        async with AsyncTransaction() as session:
            kb = await pipeline_service.kb_service.repo.get_by_pk(session, kb_id)
            if not kb:
                logger.error(f"Knowledge base with ID '{kb_id}' not found.")
                return
            default_chunking_config = kb.default_chunking_config
            embedding_config_raw = kb.embedding_config
            kb_language = kb.language if kb else "en"

        parsed_data_path = document_info.get("parsed_data_path")
        if not parsed_data_path:
            logger.error(f"Document {msg.document_id} has no parsed artifact path in document_info.")
            return

        resolved_chunking_config = (
            chunking_config_override if chunking_config_override is not None else default_chunking_config
        )
        embedding_config = resolve_knowledge_embedding_config(embedding_config_raw, language=kb_language)

        # 2. Load parsed artifact from storage
        try:
            parsed_doc = await load_parsed_document_from_storage(parsed_data_path)
        except Exception as exc:
            logger.error(f"Failed to load parsed document from {parsed_data_path}: {exc}")
            raise exc

        # 3. Run the chunker
        logger.info(f"Worker starting chunk stage for document {msg.document_id}")
        await pipeline_service.rebuild_chunks(
            document_id=msg.document_id,
            filename=msg.filename,
            parsed_doc=parsed_doc,
            chunking_config=resolved_chunking_config,
            embedding_config=embedding_config,
            stage_context=PipelineStageContext(
                name_prefix="Chunk",
                failure_detail_prefix="Ingestion",
                record_history=True,
            ),
        )

        # 4. Chain: Dispatch to handle_embed
        logger.info(f"Worker completed chunk stage. Dispatching embed task for {msg.document_id}")
        from app.features.knowledge.knowledge_base_documents.schemas import get_queue_name, map_priority_to_int

        kicker = handle_embed.kicker().with_labels(
            queue_name=get_queue_name(msg.priority, stage="embed"),
            priority=map_priority_to_int(msg.priority),
        )
        await kicker.kiq(
            EmbedDocumentMessage(
                document_id=msg.document_id,
                knowledge_base_id=msg.knowledge_base_id,
                filename=msg.filename,
                priority=msg.priority,
            )
        )

    except Exception as exc:
        logger.error(f"Chunk worker execution failed for document {msg.document_id}: {exc}")
        await _update_status_to_failed(pipeline_service, msg.document_id, error_message=str(exc))
        raise exc


@broker.task(task_name="embed_document")
@retry(stop=stop_after_attempt(3))
async def handle_embed(msg: EmbedDocumentMessage) -> None:
    """Process a document embedding stage.

    Retrieves the document and knowledge base details from DB, loads chunked
    document from MinIO, then runs the embedder.
    """
    logger.info(f"Worker received embed message for document {msg.document_id}")

    pipeline_service = build_pipeline_service()

    try:
        # 1. Retrieve document and mark status inside a short locked transaction
        async with AsyncTransaction() as session:
            doc = await pipeline_service.doc_service.repo.get_by_pk_for_update(session, msg.document_id)
            if not doc:
                logger.error(f"Document with ID '{msg.document_id}' not found.")
                return

            if doc.status == KnowledgeBaseDocumentStatus.COMPLETED:
                logger.info(f"Document {msg.document_id} is already in state {doc.status}. Skipping embed stage.")
                return

            # Mark status as EMBEDDING immediately inside lock
            doc.status = KnowledgeBaseDocumentStatus.EMBEDDING
            await session.flush()

            kb_id = doc.knowledge_base_id
            document_info = dict(doc.document_info or {})

        # 2. Retrieve knowledge base details outside the lock to prevent pool starvation
        async with AsyncTransaction() as session:
            kb = await pipeline_service.kb_service.repo.get_by_pk(session, kb_id)
            if not kb:
                logger.error(f"Knowledge base with ID '{kb_id}' not found.")
                return
            embedding_config_raw = kb.embedding_config
            previous_embed_config_hash = kb.embed_config_hash
            kb_language = kb.language if kb else "en"

        chunked_data_path = document_info.get("chunked_data_path")
        if not chunked_data_path:
            logger.error(f"Document {msg.document_id} has no chunked artifact path in document_info.")
            return

        embedding_config = resolve_knowledge_embedding_config(embedding_config_raw, language=kb_language)

        # 2. Load chunked artifact from storage
        try:
            chunks = await load_chunked_document_from_storage(chunked_data_path)
        except Exception as exc:
            logger.error(f"Failed to load chunked document from {chunked_data_path}: {exc}")
            raise exc

        # 3. Run the embedder
        logger.info(f"Worker starting embed stage for document {msg.document_id}")
        await pipeline_service.embed_chunks(
            document_id=msg.document_id,
            filename=msg.filename,
            knowledge_base_id=msg.knowledge_base_id,
            chunks=chunks,
            embedding_config=embedding_config,
            previous_embed_config_hash=previous_embed_config_hash,
            stage_context=PipelineStageContext(
                name_prefix="Embedding",
                failure_detail_prefix="Ingestion",
            ),
        )

        logger.info(f"Worker completed ingest for document {msg.document_id}")

    except Exception as exc:
        logger.error(f"Embed worker execution failed for document {msg.document_id}: {exc}")
        await _update_status_to_failed(pipeline_service, msg.document_id, error_message=str(exc))
        raise exc


async def _update_status_to_failed(pipeline_service, document_id, error_message: str | None = None) -> None:
    try:
        async with AsyncTransaction() as session:
            stmt = (
                update(KnowledgeBaseDocument)
                .where(KnowledgeBaseDocument.id == document_id)
                .values(status=KnowledgeBaseDocumentStatus.FAILED, error_message=error_message)
            )
            await session.execute(stmt)
            await session.flush()
            await refresh_knowledge_base_status_for_document(
                session,
                pipeline_service.kb_service,
                pipeline_service.doc_service,
                document_id,
            )
    except Exception as db_exc:
        logger.error(f"Failed to update document status to FAILED in catch block: {db_exc}")
