from datetime import UTC, datetime, timedelta

from app.features.knowledge.knowledge_base_documents.repos import KnowledgeBaseDocumentRepository
from app.features.knowledge.knowledge_base_documents.schemas import (
    KnowledgeBaseDocumentStatus,
    ParseDocumentMessage,
)
from app.features.knowledge.knowledge_bases.models import KnowledgeBase
from app.worker.scheduling import enqueue_parse_document_message
from app_layer_base.core.database.transaction import AsyncTransaction
from faststream.redis import RedisBroker
from loguru import logger
from rag_core.parsers import resolve_knowledge_parsing_config
from sqlalchemy import select

# If stuck in QUEUED status for longer than this duration, consider it stuck
STUCK_THRESHOLD_MINUTES = 5
MAX_RECOVERY_LIMIT = 100


async def recover_stuck_documents(broker: RedisBroker) -> None:
    """Find documents stuck in QUEUED status and re-publish them.

    Uses a chunk limit to prevent memory exhaustion (OOM) and updates the
    updated_at timestamp after re-publishing to prevent duplicate recovery triggers.
    """
    threshold = datetime.now(UTC) - timedelta(minutes=STUCK_THRESHOLD_MINUTES)
    repo = KnowledgeBaseDocumentRepository()

    async with AsyncTransaction() as session:
        # Use direct SQLAlchemy select query to apply limit chunking instead of get_all
        stmt = (
            select(repo.model)
            .where(
                repo.model.status == KnowledgeBaseDocumentStatus.QUEUED,
                repo.model.updated_at < threshold,
            )
            .limit(MAX_RECOVERY_LIMIT)
        )
        result = await session.scalars(stmt)
        stuck_docs = result.all()

        if not stuck_docs:
            logger.info("No stuck documents found to recover.")
            return

        logger.info(f"Found {len(stuck_docs)} stuck document(s) in QUEUED status. Recovering...")

        kb_ids = {doc.knowledge_base_id for doc in stuck_docs}
        kbs_result = await session.execute(select(KnowledgeBase).where(KnowledgeBase.id.in_(kb_ids)))
        kbs_map = {kb.id: kb for kb in kbs_result.scalars().all()}

        for doc in stuck_docs:
            logger.warning(f"Recovering stuck document: {doc.id} (status: {doc.status})")
            kb = kbs_map.get(doc.knowledge_base_id)
            if not kb:
                logger.error(f"KnowledgeBase {doc.knowledge_base_id} not found for document {doc.id}")
                continue

            try:
                resolved_config = resolve_knowledge_parsing_config(
                    doc.parsing_config if doc.parsing_config is not None else kb.default_parsing_config
                )
                provider = resolved_config.get_provider_for_filename(doc.name)

                msg = ParseDocumentMessage(
                    document_id=doc.id,
                    knowledge_base_id=doc.knowledge_base_id,
                    file_hash=doc.file_hash,
                    filename=doc.name,
                    content_type=doc.document_info.get("content_type") if doc.document_info else None,
                    provider=provider,
                )

                await enqueue_parse_document_message(doc.knowledge_base_id, msg, provider)
                # Update updated_at on successful publish to prevent duplicate scanning in the next cycle
                doc.updated_at = datetime.now(UTC)
            except Exception as exc:
                logger.error(f"Failed to publish recovery message for stuck document {doc.id}: {exc}")
