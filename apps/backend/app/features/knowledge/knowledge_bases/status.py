from collections.abc import Iterable
from uuid import UUID

from app.features.knowledge.knowledge_base_documents.schemas import KnowledgeBaseDocumentStatus
from app.features.knowledge.knowledge_base_documents.services import KnowledgeBaseDocumentService
from app.features.knowledge.knowledge_bases.schemas import KnowledgeBaseStatus
from app.features.knowledge.knowledge_bases.services import KnowledgeBaseService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

RUNNING_DOCUMENT_STATUSES: set[str] = {
    KnowledgeBaseDocumentStatus.QUEUED.value,
    KnowledgeBaseDocumentStatus.PARSING.value,
    KnowledgeBaseDocumentStatus.CHUNKING.value,
    KnowledgeBaseDocumentStatus.EMBEDDING.value,
    KnowledgeBaseDocumentStatus.PENDING_REPARSE.value,
    KnowledgeBaseDocumentStatus.PENDING_RECHUNK.value,
    KnowledgeBaseDocumentStatus.PENDING_REEMBED.value,
    KnowledgeBaseDocumentStatus.DELETING.value,
}


def resolve_knowledge_base_status(
    document_statuses: Iterable[str],
    *,
    current_status: str | None = None,
) -> KnowledgeBaseStatus:
    if current_status == KnowledgeBaseStatus.DELETING.value:
        return KnowledgeBaseStatus.DELETING

    statuses = set(document_statuses)
    if not statuses:
        return KnowledgeBaseStatus.READY
    if statuses & RUNNING_DOCUMENT_STATUSES:
        return KnowledgeBaseStatus.RUNNING
    if KnowledgeBaseDocumentStatus.FAILED.value in statuses:
        return KnowledgeBaseStatus.FAILED
    if statuses == {KnowledgeBaseDocumentStatus.COMPLETED.value}:
        return KnowledgeBaseStatus.COMPLETED
    return KnowledgeBaseStatus.READY


async def refresh_knowledge_base_status(
    session: AsyncSession,
    kb_service: KnowledgeBaseService,
    doc_service: KnowledgeBaseDocumentService,
    knowledge_base_id: UUID,
) -> KnowledgeBaseStatus | None:
    await session.flush()
    kb = await kb_service.repo.get_by_pk(session, knowledge_base_id)
    if not kb:
        return None

    stmt = (
        select(doc_service.repo.model.status)
        .where(doc_service.repo.model.knowledge_base_id == knowledge_base_id)
        .distinct()
    )
    result = await session.execute(stmt)
    statuses = [str(s) for s in result.scalars().all()]
    next_status = resolve_knowledge_base_status(statuses, current_status=kb.status)
    kb.status = next_status
    await session.flush()
    await session.refresh(kb)
    return next_status


async def refresh_knowledge_base_status_for_document(
    session: AsyncSession,
    kb_service: KnowledgeBaseService,
    doc_service: KnowledgeBaseDocumentService,
    document_id: UUID,
) -> KnowledgeBaseStatus | None:
    await session.flush()
    doc = await doc_service.repo.get_by_pk(session, document_id)
    if not doc:
        return None
    return await refresh_knowledge_base_status(session, kb_service, doc_service, doc.knowledge_base_id)
