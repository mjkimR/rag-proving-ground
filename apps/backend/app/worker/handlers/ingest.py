from app.features.knowledge.knowledge_base_documents.facade.pipeline import knowledge_original_file_key
from app.features.knowledge.knowledge_base_documents.schemas import (
    IngestDocumentMessage,
    KnowledgeBaseDocumentStatus,
)
from app.worker.services import build_pipeline_service
from app_file_storage import get_storage_client
from app_layer_base.core.database.transaction import AsyncTransaction
from faststream.redis import RedisRouter
from loguru import logger
from rag_core.embeddings import resolve_knowledge_embedding_config
from tenacity import retry, stop_after_attempt

router = RedisRouter()


@router.subscriber("document.ingest")
@retry(stop=stop_after_attempt(3))
async def handle_ingest(msg: IngestDocumentMessage) -> None:
    """Process a document ingestion message.

    Retrieves the document and knowledge base from DB, downloads the file from
    MinIO, then runs the full parse → chunk → embed pipeline.
    """
    logger.info(f"Worker received ingest message for document {msg.document_id}")

    pipeline_service = build_pipeline_service()

    try:
        # 1. Retrieve document and knowledge base details from DB
        async with AsyncTransaction() as session:
            kb = await pipeline_service.kb_service.repo.get_by_pk(session, msg.knowledge_base_id)
            if not kb:
                logger.error(f"Knowledge base with ID '{msg.knowledge_base_id}' not found.")
                return

            doc = await pipeline_service.doc_service.repo.get_by_pk(session, msg.document_id)
            if not doc:
                logger.error(f"Document with ID '{msg.document_id}' not found.")
                return

            kb_name = kb.name
            resolved_parsing_config = (
                doc.parsing_config if doc.parsing_config is not None else kb.default_parsing_config
            )
            resolved_chunking_config = (
                doc.chunking_config if doc.chunking_config is not None else kb.default_chunking_config
            )
            embedding_config = resolve_knowledge_embedding_config(kb.embedding_config)
            previous_embed_config_hash = kb.embed_config_hash

        # 2. Download raw file from MinIO
        storage_client = get_storage_client()
        original_file_key = knowledge_original_file_key(kb_name, msg.file_hash, msg.filename)
        try:
            content = await storage_client.download_file(original_file_key)
        except Exception as exc:
            logger.error(f"Failed to download file {original_file_key} from storage: {exc}")
            raise exc

        # 3. Run the parser, chunker, and embedding pipeline
        logger.info(f"Worker starting parse stage for document {msg.document_id}")
        parsed_doc = await pipeline_service.parse_or_load_cached(
            document_id=msg.document_id,
            knowledge_base_name=kb_name,
            file_hash=msg.file_hash,
            filename=msg.filename,
            content=content,
            content_type=msg.content_type,
            parsing_config=resolved_parsing_config,
            provider_override=msg.provider,
        )

        logger.info(f"Worker starting chunk stage for document {msg.document_id}")
        chunks = await pipeline_service.rebuild_chunks(
            document_id=msg.document_id,
            filename=msg.filename,
            parsed_doc=parsed_doc,
            chunking_config=resolved_chunking_config,
            record_history=True,
            history_name_prefix="Chunk",
            failure_detail_prefix="Ingestion",
        )

        logger.info(f"Worker starting embed stage for document {msg.document_id}")
        await pipeline_service.embed_chunks(
            document_id=msg.document_id,
            filename=msg.filename,
            knowledge_base_id=msg.knowledge_base_id,
            chunks=chunks,
            embedding_config=embedding_config,
            previous_embed_config_hash=previous_embed_config_hash,
            history_name_prefix="Embedding",
            failure_detail_prefix="Ingestion",
        )

        logger.info(f"Worker completed ingest for document {msg.document_id}")

    except Exception as exc:
        logger.error(f"Ingest worker execution failed for document {msg.document_id}: {exc}")
        try:
            async with AsyncTransaction() as session:
                await pipeline_service.doc_service.repo.update_by_pk(
                    session, msg.document_id, {"status": KnowledgeBaseDocumentStatus.FAILED}
                )
        except Exception as db_exc:
            logger.error(f"Failed to update document status to FAILED in catch block: {db_exc}")
        raise exc
