from datetime import timedelta
from typing import Any

from app_layer_base.core.database.transaction import AsyncTransaction
from loguru import logger
from sqlalchemy import or_, select

from app.common.utils.time_util import get_current_time
from app.features.knowledge.knowledge_base_documents.repos import KnowledgeBaseDocumentRepository
from app.features.knowledge.knowledge_base_documents.schemas import KnowledgeBaseDocumentStatus

# If stuck in QUEUED status for longer than this, or processing for longer than 15 minutes, consider it stuck
STUCK_QUEUED_THRESHOLD_MINUTES = 5
STUCK_PROCESSING_THRESHOLD_MINUTES = 15
MAX_RECOVERY_LIMIT = 100


async def recover_stuck_documents(broker: Any) -> None:
    """Find documents stuck in QUEUED or active processing states (PARSING, CHUNKING, EMBEDDING)

    for too long, and reset them to QUEUED status so the DB-polling scheduler can retry them.
    """
    now = get_current_time()
    queued_threshold = now - timedelta(minutes=STUCK_QUEUED_THRESHOLD_MINUTES)
    processing_threshold = now - timedelta(minutes=STUCK_PROCESSING_THRESHOLD_MINUTES)

    repo = KnowledgeBaseDocumentRepository()

    async with AsyncTransaction() as session:
        # Query documents stuck in QUEUED for >5m, or PARSING/CHUNKING/EMBEDDING for >15m
        stmt = (
            select(repo.model)
            .where(
                or_(
                    (repo.model.status == KnowledgeBaseDocumentStatus.QUEUED)
                    & (repo.model.updated_at < queued_threshold),
                    (
                        repo.model.status.in_(
                            [
                                KnowledgeBaseDocumentStatus.PARSING,
                                KnowledgeBaseDocumentStatus.CHUNKING,
                                KnowledgeBaseDocumentStatus.EMBEDDING,
                            ]
                        )
                    )
                    & (repo.model.updated_at < processing_threshold),
                )
            )
            .limit(MAX_RECOVERY_LIMIT)
        )
        result = await session.scalars(stmt)
        stuck_docs = result.all()

        if not stuck_docs:
            logger.info("No stuck documents found to recover.")
            return

        logger.info(
            f"Found {len(stuck_docs)} stuck document(s) in active/queued states. Resetting to QUEUED for retry..."
        )

        for doc in stuck_docs:
            logger.warning(
                f"Recovering stuck document: {doc.id} (current status: {doc.status}, updated_at: {doc.updated_at})"
            )
            doc.status = KnowledgeBaseDocumentStatus.QUEUED
            doc.updated_at = now
