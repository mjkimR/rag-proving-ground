from typing import Annotated
from uuid import UUID

from app.features.providers.document_parsers.schemas import (
    DocumentParserCreate,
    DocumentParserPatch,
    DocumentParserPut,
    DocumentParserRead,
)
from app.features.providers.document_parsers.usecases.crud import (
    CreateDocumentParserUseCase,
    DeleteDocumentParserUseCase,
    GetDocumentParserUseCase,
    GetMultiDocumentParserUseCase,
    PatchDocumentParserUseCase,
    PutDocumentParserUseCase,
)
from app.features.providers.document_parsers.usecases.sync import SyncDocumentParsersUseCase
from app.features.providers.document_parsers.usecases.test import TestDocumentParserConnectionUseCase
from app_layer_base.base.deps.params.page import PaginationParam
from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.schemas.delete_resp import DeleteResponse
from app_layer_base.base.schemas.paginated import PaginatedList
from fastapi import APIRouter, Depends, status

router = APIRouter(prefix="/document_parsers", tags=["DocumentParser"], dependencies=[])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DocumentParserRead)
async def create_document_parser(
    use_case: Annotated[CreateDocumentParserUseCase, Depends()],
    document_parser_in: DocumentParserCreate,
):
    return await use_case.execute(document_parser_in)


@router.get("", response_model=PaginatedList[DocumentParserRead])
async def get_document_parsers(
    use_case: Annotated[GetMultiDocumentParserUseCase, Depends()],
    pagination: PaginationParam,
):
    query_options = ListQueryOptions(offset=pagination.offset, limit=pagination.limit)
    return await use_case.execute(query_options=query_options)


@router.get("/{document_parser_id}", response_model=DocumentParserRead)
async def get_document_parser(
    use_case: Annotated[GetDocumentParserUseCase, Depends()],
    document_parser_id: UUID,
):
    document_parser = await use_case.execute(document_parser_id)
    if not document_parser:
        raise NotFoundException()
    return document_parser


@router.patch("/{document_parser_id}", response_model=DocumentParserRead)
async def patch_document_parser(
    use_case: Annotated[PatchDocumentParserUseCase, Depends()],
    document_parser_id: UUID,
    document_parser_in: DocumentParserPatch,
):
    document_parser = await use_case.execute(document_parser_id, document_parser_in)
    if not document_parser:
        raise NotFoundException()
    return document_parser


@router.put("/{document_parser_id}", response_model=DocumentParserRead)
async def put_document_parser(
    use_case: Annotated[PutDocumentParserUseCase, Depends()],
    document_parser_id: UUID,
    document_parser_in: DocumentParserPut,
):
    document_parser = await use_case.execute(document_parser_id, document_parser_in)
    if not document_parser:
        raise NotFoundException()
    return document_parser


@router.delete("/{document_parser_id}", response_model=DeleteResponse)
async def delete_document_parser(
    use_case: Annotated[DeleteDocumentParserUseCase, Depends()],
    document_parser_id: UUID,
):
    return await use_case.execute(document_parser_id)


@router.post("/sync", response_model=list[DocumentParserRead])
async def sync_document_parsers(
    use_case: Annotated[SyncDocumentParsersUseCase, Depends()],
):
    return await use_case.execute()


@router.post("/{document_parser_id}/test")
async def test_document_parser(
    use_case: Annotated[TestDocumentParserConnectionUseCase, Depends()],
    document_parser_id: UUID,
):
    return await use_case.execute(document_parser_id)
