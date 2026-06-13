from typing import Annotated, Any

from app.features.providers.document_parsers.models import DocumentParser
from app.features.providers.document_parsers.schemas import (
    DocumentParserCreate,
    DocumentParserPatch,
    DocumentParserPut,
)
from app.features.providers.document_parsers.services import (
    DocumentParserContextKwargs,
    DocumentParserService,
)
from app.features.providers.routes.cache import refresh_document_parsers_cache
from app_layer_base.base.repos.base import PrimaryKeyType
from app_layer_base.base.usecases.crud import (
    BaseCreateUseCase,
    BaseDeleteUseCase,
    BaseGetMultiUseCase,
    BaseGetUseCase,
    BasePatchUseCase,
    BasePutUseCase,
)
from fastapi import Depends
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession


class GetDocumentParserUseCase(BaseGetUseCase[DocumentParserService, DocumentParser, DocumentParserContextKwargs]):
    def __init__(self, service: Annotated[DocumentParserService, Depends()]) -> None:
        super().__init__(service)


class GetMultiDocumentParserUseCase(
    BaseGetMultiUseCase[DocumentParserService, DocumentParser, DocumentParserContextKwargs]
):
    def __init__(self, service: Annotated[DocumentParserService, Depends()]) -> None:
        super().__init__(service)


class CreateDocumentParserUseCase(
    BaseCreateUseCase[DocumentParserService, DocumentParser, DocumentParserCreate, DocumentParserContextKwargs]
):
    def __init__(self, service: Annotated[DocumentParserService, Depends()]) -> None:
        super().__init__(service)

    async def _execute(
        self,
        session: AsyncSession,
        obj_data: DocumentParserCreate,
        context: DocumentParserContextKwargs | None,
    ) -> DocumentParser:
        if obj_data.is_default:
            await session.execute(update(DocumentParser).values(is_default=False))
        created = await super()._execute(session, obj_data, context)
        await refresh_document_parsers_cache(session)
        return created


class PatchDocumentParserUseCase(
    BasePatchUseCase[
        DocumentParserService, DocumentParser, DocumentParserPut, DocumentParserPatch, DocumentParserContextKwargs
    ]
):
    def __init__(self, service: Annotated[DocumentParserService, Depends()]) -> None:
        super().__init__(service)

    async def _execute(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: DocumentParserPatch,
        context: DocumentParserContextKwargs | None,
    ) -> DocumentParser | None:
        if obj_data.is_default:
            await session.execute(update(DocumentParser).values(is_default=False))
        updated = await super()._execute(session, obj_pk, obj_data, context)
        await refresh_document_parsers_cache(session)
        return updated


class PutDocumentParserUseCase(
    BasePutUseCase[
        DocumentParserService, DocumentParser, DocumentParserPut, DocumentParserPatch, DocumentParserContextKwargs
    ]
):
    def __init__(self, service: Annotated[DocumentParserService, Depends()]) -> None:
        super().__init__(service)

    async def _execute(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: DocumentParserPut,
        context: DocumentParserContextKwargs | None,
    ) -> DocumentParser | None:
        if obj_data.is_default:
            await session.execute(update(DocumentParser).values(is_default=False))
        updated = await super()._execute(session, obj_pk, obj_data, context)
        await refresh_document_parsers_cache(session)
        return updated


class DeleteDocumentParserUseCase(
    BaseDeleteUseCase[DocumentParserService, DocumentParser, DocumentParserContextKwargs]
):
    def __init__(self, service: Annotated[DocumentParserService, Depends()]) -> None:
        super().__init__(service)

    async def _execute(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        context: DocumentParserContextKwargs | None,
    ) -> Any:
        deleted = await super()._execute(session, obj_pk, context)
        await refresh_document_parsers_cache(session)
        return deleted
