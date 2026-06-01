from datetime import UTC, datetime, timedelta

from app.features.knowledge.knowledge_base_documents.repos import KnowledgeBaseDocumentRepository
from app.features.knowledge.knowledge_base_documents.schemas import (
    IngestDocumentMessage,
    KnowledgeBaseDocumentStatus,
)
from app_layer_base.core.database.transaction import AsyncTransaction
from faststream.redis import RedisBroker
from loguru import logger
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
        for doc in stuck_docs:
            logger.warning(f"Recovering stuck document: {doc.id} (status: {doc.status})")
            try:
                await broker.publish(
                    IngestDocumentMessage(
                        document_id=doc.id,
                        knowledge_base_id=doc.knowledge_base_id,
                        file_hash=doc.file_hash,
                        filename=doc.name,
                        content_type=doc.document_info.get("content_type") if doc.document_info else None,
                    ),
                    "document.ingest",
                )
                # Update updated_at on successful publish to prevent duplicate scanning in the next cycle
                doc.updated_at = datetime.now(UTC)
            except Exception as exc:
                logger.error(f"Failed to publish recovery message for stuck document {doc.id}: {exc}")
