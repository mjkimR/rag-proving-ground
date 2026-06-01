from app.features.knowledge.knowledge_base_documents.facade.pipeline import load_parsed_document_from_storage
from app.features.knowledge.knowledge_base_documents.schemas import (
    KnowledgeBaseDocumentReprocessMode,
    KnowledgeBaseDocumentStatus,
    ReprocessDocumentMessage,
)
from app.worker.services import build_pipeline_service
from app_layer_base.core.database.transaction import AsyncTransaction
from faststream.redis import RedisRouter
from loguru import logger
from rag_core.embeddings import resolve_knowledge_embedding_config
from tenacity import retry, stop_after_attempt

router = RedisRouter()


@router.subscriber("document.reprocess")
@retry(stop=stop_after_attempt(3))
async def handle_reprocess(msg: ReprocessDocumentMessage) -> None:
    """Process a document reprocessing message.

    Loads the parsed document from storage, then runs the rebuild_chunks →
    embed_chunks pipeline.
    """
    logger.info(f"Worker received reprocess message for document {msg.document_id} with mode {msg.mode}")

    pipeline_service = build_pipeline_service()

    try:
        # 1. Retrieve document and knowledge base details from DB
        async with AsyncTransaction() as session:
            doc = await pipeline_service.doc_service.repo.get_by_pk(session, msg.document_id)
            if not doc:
                logger.error(f"Document with ID '{msg.document_id}' not found.")
                return

            kb = await pipeline_service.kb_service.repo.get_by_pk(session, doc.knowledge_base_id)
            if not kb:
                logger.error(f"Knowledge base with ID '{doc.knowledge_base_id}' not found.")
                return

            document_info = dict(doc.document_info or {})
            parsed_data_path = document_info.get("parsed_data_path")
            if not parsed_data_path:
                logger.error(f"Document {msg.document_id} has no parsed artifact path in document_info.")
                return

            filename = doc.name
            knowledge_base_id = doc.knowledge_base_id
            resolved_chunking_config = (
                doc.chunking_config if doc.chunking_config is not None else kb.default_chunking_config
            )
            embedding_config = resolve_knowledge_embedding_config(kb.embedding_config)
            previous_embed_config_hash = kb.embed_config_hash

        # 2. Load parsed artifact from local or S3 storage
        try:
            parsed_doc = await load_parsed_document_from_storage(parsed_data_path)
        except Exception as exc:
            logger.error(f"Failed to load parsed document from {parsed_data_path}: {exc}")
            raise exc

        # 3. Run the re-chunking and re-embedding pipeline
        logger.info(f"Worker starting chunk rebuild stage for document {msg.document_id}")
        chunks = await pipeline_service.rebuild_chunks(
            document_id=msg.document_id,
            filename=filename,
            parsed_doc=parsed_doc,
            chunking_config=resolved_chunking_config,
            record_history=msg.mode == KnowledgeBaseDocumentReprocessMode.RECHUNK,
            history_name_prefix="Rechunk",
            failure_detail_prefix="Document reprocessing",
        )

        logger.info(f"Worker starting re-embedding stage for document {msg.document_id}")
        await pipeline_service.embed_chunks(
            document_id=msg.document_id,
            filename=filename,
            knowledge_base_id=knowledge_base_id,
            chunks=chunks,
            embedding_config=embedding_config,
            previous_embed_config_hash=previous_embed_config_hash,
            history_name_prefix="Reembedding",
            failure_detail_prefix="Document reprocessing",
        )

        logger.info(f"Worker completed reprocess for document {msg.document_id}")

    except Exception as exc:
        logger.error(f"Reprocess worker execution failed for document {msg.document_id}: {exc}")
        try:
            async with AsyncTransaction() as session:
                await pipeline_service.doc_service.repo.update_by_pk(
                    session, msg.document_id, {"status": KnowledgeBaseDocumentStatus.FAILED}
                )
        except Exception as db_exc:
            logger.error(f"Failed to update document status to FAILED in catch block: {db_exc}")
        raise exc
