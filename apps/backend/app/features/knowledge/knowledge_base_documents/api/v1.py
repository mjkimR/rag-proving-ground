from typing import Annotated
from uuid import UUID

from app.features.knowledge.knowledge_base_documents.schemas import (
    KnowledgeBaseDocumentCreate,
    KnowledgeBaseDocumentPatch,
    KnowledgeBaseDocumentPut,
    KnowledgeBaseDocumentRead,
)
from app.features.knowledge.knowledge_base_documents.services import KnowledgeBaseDocumentService
from app.features.knowledge.knowledge_base_documents.usecases.crud import (
    CreateKnowledgeBaseDocumentUseCase,
    DeleteKnowledgeBaseDocumentUseCase,
    GetKnowledgeBaseDocumentUseCase,
    GetMultiKnowledgeBaseDocumentUseCase,
    PatchKnowledgeBaseDocumentUseCase,
    PutKnowledgeBaseDocumentUseCase,
)
from app_layer_base.base.deps.params.page import PaginationParam
from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.schemas.delete_resp import DeleteResponse
from app_layer_base.base.schemas.paginated import PaginatedList
from fastapi import APIRouter, Depends, status

router = APIRouter(prefix="/knowledge_base_documents", tags=["KnowledgeBaseDocument"], dependencies=[])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=KnowledgeBaseDocumentRead)
async def create_knowledge_base_document(
    use_case: Annotated[CreateKnowledgeBaseDocumentUseCase, Depends()],
    knowledge_base_document_in: KnowledgeBaseDocumentCreate,
):
    return await use_case.execute(knowledge_base_document_in)


@router.get("", response_model=PaginatedList[KnowledgeBaseDocumentRead])
async def get_knowledge_base_documents(
    use_case: Annotated[GetMultiKnowledgeBaseDocumentUseCase, Depends()],
    pagination: PaginationParam,
):
    query_options = ListQueryOptions(offset=pagination.offset, limit=pagination.limit)
    return await use_case.execute(query_options=query_options)


@router.get("/{knowledge_base_document_id}", response_model=KnowledgeBaseDocumentRead)
async def get_knowledge_base_document(
    use_case: Annotated[GetKnowledgeBaseDocumentUseCase, Depends()],
    knowledge_base_document_id: UUID,
):
    knowledge_base_document = await use_case.execute(knowledge_base_document_id)
    if not knowledge_base_document:
        raise NotFoundException()
    return knowledge_base_document


@router.patch("/{knowledge_base_document_id}", response_model=KnowledgeBaseDocumentRead)
async def patch_knowledge_base_document(
    use_case: Annotated[PatchKnowledgeBaseDocumentUseCase, Depends()],
    knowledge_base_document_id: UUID,
    knowledge_base_document_in: KnowledgeBaseDocumentPatch,
):
    knowledge_base_document = await use_case.execute(knowledge_base_document_id, knowledge_base_document_in)
    if not knowledge_base_document:
        raise NotFoundException()
    return knowledge_base_document


@router.put("/{knowledge_base_document_id}", response_model=KnowledgeBaseDocumentRead)
async def put_knowledge_base_document(
    use_case: Annotated[PutKnowledgeBaseDocumentUseCase, Depends()],
    knowledge_base_document_id: UUID,
    knowledge_base_document_in: KnowledgeBaseDocumentPut,
):
    knowledge_base_document = await use_case.execute(knowledge_base_document_id, knowledge_base_document_in)
    if not knowledge_base_document:
        raise NotFoundException()
    return knowledge_base_document


@router.delete("/{knowledge_base_document_id}", response_model=DeleteResponse)
async def delete_knowledge_base_document(
    use_case: Annotated[DeleteKnowledgeBaseDocumentUseCase, Depends()],
    knowledge_base_document_id: UUID,
):
    return await use_case.execute(knowledge_base_document_id)


@router.get("/{knowledge_base_document_id}/download", status_code=status.HTTP_200_OK)
async def download_knowledge_base_document(
    knowledge_base_document_id: UUID,
    doc_service: Annotated[KnowledgeBaseDocumentService, Depends()],
):
    """Download the original uploaded document from storage."""
    import urllib.parse

    from app_file_storage import get_storage_client
    from app_layer_base.core.database.transaction import AsyncTransaction
    from fastapi.responses import StreamingResponse

    async with AsyncTransaction() as session:
        doc = await doc_service.repo.get_by_pk(session, knowledge_base_document_id)
        if not doc or not doc.document_info:
            raise NotFoundException("Document not found or has no storage info.")
        original_file_key = doc.document_info.get("original_file_path")
        filename = doc.document_info.get("filename")

    if not original_file_key:
        raise NotFoundException("Original file storage key is missing.")

    encoded_filename = urllib.parse.quote(filename or "file")
    storage_client = get_storage_client()

    async def file_streamer():
        async for chunk in storage_client.download_file_stream(original_file_key):
            yield chunk

    return StreamingResponse(
        file_streamer(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=utf-8''{encoded_filename}"},
    )


@router.get("/{knowledge_base_document_id}/parsed", status_code=status.HTTP_200_OK)
async def get_parsed_document(
    knowledge_base_document_id: UUID,
    doc_service: Annotated[KnowledgeBaseDocumentService, Depends()],
):
    """Get the parsed elements document structure (parsed_data.json) for a document."""
    import json

    from app_file_storage import get_storage_client
    from app_layer_base.core.database.transaction import AsyncTransaction
    from rag_core.parsers.schemas import ParsedDocument

    async with AsyncTransaction() as session:
        doc = await doc_service.repo.get_by_pk(session, knowledge_base_document_id)
        if not doc or not doc.document_info:
            raise NotFoundException("Document not found or has no storage info.")
        parsed_data_path = doc.document_info.get("parsed_data_path")

    if not parsed_data_path:
        raise NotFoundException("Parsed data storage key is missing.")

    storage_client = get_storage_client()
    if not await storage_client.file_exists(parsed_data_path):
        raise NotFoundException("Parsed document data not found in storage.")

    data = await storage_client.download_file(parsed_data_path)
    return ParsedDocument(**json.loads(data.decode("utf-8")))
