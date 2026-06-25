from typing import Annotated

from app.features.providers.document_parsers.models import DocumentParser
from app.features.providers.document_parsers.schemas import DocumentParserCreate
from app.features.providers.document_parsers.services import DocumentParserService
from app.features.providers.routes.cache import refresh_document_parsers_cache
from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends
from rag_core.adapters.parser.registry import ParserRegistry
from sqlalchemy import select


class SyncDocumentParsersUseCase(BaseUseCase):
    def __init__(self, service: Annotated[DocumentParserService, Depends()]) -> None:
        self.service = service

    async def execute(self) -> list[DocumentParser]:
        # Fetch registered parser providers
        parsers_list = ParserRegistry.list_parsers()

        async with AsyncTransaction() as session:
            # Query existing parsers in DB
            stmt = select(DocumentParser)
            res = await session.execute(stmt)
            existing_parsers = {p.name: p for p in res.scalars().all()}

            new_parsers = []
            for name in parsers_list:
                if name not in existing_parsers:
                    # New parser discovered, create record schema
                    new_parsers.append(
                        DocumentParserCreate(
                            name=name,
                            is_active=True,
                            is_default=False,
                            connection_info={},
                            extra_metadata={},
                        )
                    )

            if new_parsers:
                await self.service.create_multi(session, new_parsers)

            await session.flush()
            # Reload registry cache
            await refresh_document_parsers_cache(session)

            # Fetch all from DB to return complete list
            stmt = select(DocumentParser)
            res = await session.execute(stmt)
            return list(res.scalars().all())
