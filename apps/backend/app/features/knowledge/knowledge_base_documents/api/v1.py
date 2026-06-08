from typing import Annotated
from uuid import UUID

from app.features.knowledge.knowledge_base_documents.query_options import get_knowledge_base_documents_query_options
from app.features.knowledge.knowledge_base_documents.schemas import (
    KnowledgeBaseDocumentCreate,
    KnowledgeBaseDocumentPatch,
    KnowledgeBaseDocumentPut,
    KnowledgeBaseDocumentRead,
    KnowledgeBaseDocumentReprocessRequest,
)
from app.features.knowledge.knowledge_base_documents.usecases.assets import (
    DownloadKnowledgeBaseDocumentUseCase,
    GetParsedKnowledgeBaseDocumentUseCase,
)
from app.features.knowledge.knowledge_base_documents.usecases.crud import (
    CreateKnowledgeBaseDocumentUseCase,
    DeleteKnowledgeBaseDocumentUseCase,
    GetKnowledgeBaseDocumentUseCase,
    GetMultiKnowledgeBaseDocumentUseCase,
    PatchKnowledgeBaseDocumentUseCase,
    PutKnowledgeBaseDocumentUseCase,
)
from app.features.knowledge.knowledge_base_documents.usecases.reprocess import ReprocessKnowledgeBaseDocumentUseCase
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
    query_options: Annotated[ListQueryOptions, Depends(get_knowledge_base_documents_query_options)],
):
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


@router.post(
    "/{knowledge_base_document_id}/reprocess",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=KnowledgeBaseDocumentRead,
)
async def reprocess_knowledge_base_document(
    knowledge_base_document_id: UUID,
    use_case: Annotated[ReprocessKnowledgeBaseDocumentUseCase, Depends()],
    reprocess_in: KnowledgeBaseDocumentReprocessRequest | None = None,
):
    request = reprocess_in or KnowledgeBaseDocumentReprocessRequest()
    return await use_case.execute(knowledge_base_document_id, mode=request.mode)


@router.get("/{knowledge_base_document_id}/download", status_code=status.HTTP_200_OK)
async def download_knowledge_base_document(
    knowledge_base_document_id: UUID,
    use_case: Annotated[DownloadKnowledgeBaseDocumentUseCase, Depends()],
):
    """Download the original uploaded document from storage."""
    return await use_case.execute(knowledge_base_document_id)


@router.get("/{knowledge_base_document_id}/parsed", status_code=status.HTTP_200_OK)
async def get_parsed_document(
    knowledge_base_document_id: UUID,
    use_case: Annotated[GetParsedKnowledgeBaseDocumentUseCase, Depends()],
):
    """Get the parsed elements document structure (parsed_data.json) for a document."""
    return await use_case.execute(knowledge_base_document_id)
