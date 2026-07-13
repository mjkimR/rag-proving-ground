from typing import Annotated

from app_layer_base.base.schemas.delete_resp import DeleteResponse
from app_layer_base.base.usecases.crud import (
    BaseCreateUseCase,
    BaseDeleteUseCase,
    BaseGetMultiUseCase,
    BaseGetUseCase,
    BasePatchUseCase,
    BasePutUseCase,
)
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def _post_execute(
        self,
        session: AsyncSession,
        obj: DocumentParser,
        obj_data: DocumentParserCreate,
        context: DocumentParserContextKwargs | None,
    ) -> DocumentParser:
        await refresh_document_parsers_cache(session)
        return obj


class PatchDocumentParserUseCase(
    BasePatchUseCase[
        DocumentParserService, DocumentParser, DocumentParserPut, DocumentParserPatch, DocumentParserContextKwargs
    ]
):
    def __init__(self, service: Annotated[DocumentParserService, Depends()]) -> None:
        super().__init__(service)

    async def _post_execute(
        self,
        session: AsyncSession,
        obj: DocumentParser | None,
        obj_data: DocumentParserPut | DocumentParserPatch,
        context: DocumentParserContextKwargs | None,
    ) -> DocumentParser | None:
        await refresh_document_parsers_cache(session)
        return obj


class PutDocumentParserUseCase(
    BasePutUseCase[
        DocumentParserService, DocumentParser, DocumentParserPut, DocumentParserPatch, DocumentParserContextKwargs
    ]
):
    def __init__(self, service: Annotated[DocumentParserService, Depends()]) -> None:
        super().__init__(service)

    async def _post_execute(
        self,
        session: AsyncSession,
        obj: DocumentParser | None,
        obj_data: DocumentParserPut | DocumentParserPatch,
        context: DocumentParserContextKwargs | None,
    ) -> DocumentParser | None:
        await refresh_document_parsers_cache(session)
        return obj


class DeleteDocumentParserUseCase(
    BaseDeleteUseCase[DocumentParserService, DocumentParser, DocumentParserContextKwargs]
):
    def __init__(self, service: Annotated[DocumentParserService, Depends()]) -> None:
        super().__init__(service)

    async def _post_execute(
        self,
        session: AsyncSession,
        obj: DeleteResponse,
        context: DocumentParserContextKwargs | None,
    ) -> DeleteResponse:
        await refresh_document_parsers_cache(session)
        return obj
