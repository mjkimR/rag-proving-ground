from uuid import UUID

from app.features.knowledge.knowledge_base_documents.models import KnowledgeBaseDocument
from app.features.knowledge.knowledge_base_documents.schemas import (
    KnowledgeBaseDocumentCreate,
    KnowledgeBaseDocumentPatch,
    KnowledgeBaseDocumentPut,
)
from app_layer_base.base.repos.base import BaseRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class KnowledgeBaseDocumentRepository(
    BaseRepository[
        KnowledgeBaseDocument, KnowledgeBaseDocumentCreate, KnowledgeBaseDocumentPut, KnowledgeBaseDocumentPatch
    ]
):
    model = KnowledgeBaseDocument

    async def get_by_pk_for_update(self, session: AsyncSession, pk: UUID) -> KnowledgeBaseDocument | None:
        stmt = select(self.model).where(self.model.id == pk).with_for_update()
        res = await session.execute(stmt)
        return res.scalar_one_or_none()
