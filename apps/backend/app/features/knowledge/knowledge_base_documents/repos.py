from collections.abc import Sequence
from dataclasses import replace
from uuid import UUID

from app_layer_base.base.repos.base import BaseRepository
from app_layer_base.base.repos.query_options import ListQueryOptions
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.knowledge.knowledge_base_documents.models import KnowledgeBaseDocument
from app.features.knowledge.knowledge_base_documents.schemas import (
    KnowledgeBaseDocumentCreate,
    KnowledgeBaseDocumentPatch,
    KnowledgeBaseDocumentPut,
)


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

    async def get_all_by_knowledge_base(
        self, session: AsyncSession, knowledge_base_id: UUID
    ) -> Sequence[KnowledgeBaseDocument]:
        return await self.get_all(session, where=(KnowledgeBaseDocument.knowledge_base_id == knowledge_base_id,))

    def scoped_to_knowledge_base(self, query_options: ListQueryOptions, knowledge_base_id: UUID) -> ListQueryOptions:
        """A copy of *query_options* constrained to one knowledge base."""
        where = query_options.where
        if where is None:
            where_seq: tuple = ()
        elif isinstance(where, (list, tuple)):
            where_seq = tuple(w for w in where if w is not None)
        else:
            where_seq = (where,)
        return replace(
            query_options,
            where=(*where_seq, KnowledgeBaseDocument.knowledge_base_id == knowledge_base_id),
        )
