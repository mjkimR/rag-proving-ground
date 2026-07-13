from app_layer_base.base.repos.base import BaseRepository
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.providers.document_parsers.models import DocumentParser
from app.features.providers.document_parsers.schemas import DocumentParserCreate, DocumentParserPatch, DocumentParserPut


class DocumentParserRepository(
    BaseRepository[DocumentParser, DocumentParserCreate, DocumentParserPut, DocumentParserPatch]
):
    model = DocumentParser

    async def clear_default(self, session: AsyncSession) -> None:
        """Unset is_default on every parser (there is a single global default)."""
        await session.execute(update(DocumentParser).values(is_default=False))
