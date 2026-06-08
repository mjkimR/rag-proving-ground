from uuid import UUID

from app.features.knowledge.knowledge_base_pages.models import KnowledgeBasePage
from app.features.knowledge.knowledge_base_pages.schemas import (
    KnowledgeBasePageCreate,
    KnowledgeBasePagePatch,
    KnowledgeBasePagePut,
)
from app_layer_base.base.repos.base import BaseRepository
from rag_core.retrieval import RetrievedChunk
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession


class KnowledgeBasePageRepository(
    BaseRepository[KnowledgeBasePage, KnowledgeBasePageCreate, KnowledgeBasePagePut, KnowledgeBasePagePatch]
):
    model = KnowledgeBasePage

    async def bulk_create(
        self, session: AsyncSession, pages: list[KnowledgeBasePageCreate], document_id: UUID
    ) -> list[KnowledgeBasePage]:
        db_pages = [
            KnowledgeBasePage(
                document_id=document_id,
                page_id=page.page_id,
                page_number=page.page_number,
                content=page.content,
                metadata_info=page.metadata_info,
            )
            for page in pages
        ]
        session.add_all(db_pages)
        await session.flush()
        return db_pages

    async def get_by_page_ids(self, session: AsyncSession, page_ids: list[str]) -> list[KnowledgeBasePage]:
        if not page_ids:
            return []
        stmt = select(KnowledgeBasePage).where(KnowledgeBasePage.page_id.in_(page_ids))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_document_page_pairs(
        self, session: AsyncSession, pairs: list[tuple[UUID, str]]
    ) -> list[KnowledgeBasePage]:
        if not pairs:
            return []
        from sqlalchemy import tuple_

        stmt = select(KnowledgeBasePage).where(
            tuple_(KnowledgeBasePage.document_id, KnowledgeBasePage.page_id).in_(pairs)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_document_id(self, session: AsyncSession, document_id: UUID) -> None:
        stmt = delete(KnowledgeBasePage).where(KnowledgeBasePage.document_id == document_id)
        await session.execute(stmt)
        await session.flush()

    async def enrich_chunks_with_page_content(self, session: AsyncSession, chunks: list[RetrievedChunk]) -> None:
        doc_page_pairs = set()
        fallback_page_ids = set()
        use_fallback = False

        for chunk in chunks:
            p_ids = chunk.metadata.get("page_ids")
            if isinstance(p_ids, list) and p_ids:
                if chunk.doc_id:
                    try:
                        doc_uuid = UUID(chunk.doc_id)
                        for p_id in p_ids:
                            doc_page_pairs.add((doc_uuid, p_id))
                    except ValueError:
                        use_fallback = True
                        fallback_page_ids.update(p_ids)
                else:
                    use_fallback = True
                    fallback_page_ids.update(p_ids)

        if not doc_page_pairs and not fallback_page_ids:
            return

        pages: list[KnowledgeBasePage] = []
        if doc_page_pairs:
            pages.extend(await self.get_by_document_page_pairs(session, list(doc_page_pairs)))
        if use_fallback and fallback_page_ids:
            pages.extend(await self.get_by_page_ids(session, list(fallback_page_ids)))

        page_map = {(str(page.document_id), page.page_id): page.content for page in pages}
        fallback_map = {page.page_id: page.content for page in pages}

        for chunk in chunks:
            p_ids = chunk.metadata.get("page_ids")
            if isinstance(p_ids, list) and p_ids:
                contents = []
                for p_id in p_ids:
                    page_content = page_map.get((chunk.doc_id, p_id))
                    if page_content is None:
                        page_content = fallback_map.get(p_id)
                    if page_content is not None:
                        contents.append(page_content)
                if contents:
                    chunk.page_content = "\n\n".join(contents)
