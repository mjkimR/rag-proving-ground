from typing import Annotated
from uuid import UUID

from app.features.knowledge.knowledge_base_documents.schemas import KnowledgeBaseDocumentRead
from app.features.knowledge.knowledge_base_documents.services import KnowledgeBaseDocumentService
from app.features.knowledge.knowledge_base_documents.usecases.ingest import IngestKnowledgeDocumentUseCase
from app.features.knowledge.knowledge_bases.schemas import (
    KnowledgeBaseCreate,
    KnowledgeBasePatch,
    KnowledgeBasePut,
    KnowledgeBaseRead,
    KnowledgeBaseSearchRequest,
    KnowledgeBaseSearchResponse,
    MultiKnowledgeBaseSearchRequest,
)
from app.features.knowledge.knowledge_bases.usecases.crud import (
    CreateKnowledgeBaseUseCase,
    DeleteKnowledgeBaseUseCase,
    GetKnowledgeBaseUseCase,
    GetMultiKnowledgeBaseUseCase,
    PatchKnowledgeBaseUseCase,
    PutKnowledgeBaseUseCase,
)
from app.features.knowledge.knowledge_bases.usecases.search import (
    SearchKnowledgeBaseUseCase,
    SearchMultiKnowledgeBaseUseCase,
)
from app_layer_base.base.deps.params.page import PaginationParam
from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.schemas.delete_resp import DeleteResponse
from app_layer_base.base.schemas.paginated import PaginatedList
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import APIRouter, Depends, File, Form, UploadFile, status

router = APIRouter(prefix="/knowledge_bases", tags=["KnowledgeBase"], dependencies=[])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=KnowledgeBaseRead)
async def create_knowledge_base(
    use_case: Annotated[CreateKnowledgeBaseUseCase, Depends()],
    knowledge_base_in: KnowledgeBaseCreate,
):
    return await use_case.execute(knowledge_base_in)


@router.get("", response_model=PaginatedList[KnowledgeBaseRead])
async def get_knowledge_bases(
    use_case: Annotated[GetMultiKnowledgeBaseUseCase, Depends()],
    pagination: PaginationParam,
):
    query_options = ListQueryOptions(offset=pagination.offset, limit=pagination.limit)
    return await use_case.execute(query_options=query_options)


@router.post("/search", response_model=KnowledgeBaseSearchResponse)
async def search_multi_knowledge_bases(
    use_case: Annotated[SearchMultiKnowledgeBaseUseCase, Depends()],
    search_request: MultiKnowledgeBaseSearchRequest,
):
    """Retrieve similar document chunks across one or more knowledge bases."""
    return await use_case.execute(search_request)


@router.get("/{knowledge_base_id}", response_model=KnowledgeBaseRead)
async def get_knowledge_base(
    use_case: Annotated[GetKnowledgeBaseUseCase, Depends()],
    knowledge_base_id: UUID,
):
    knowledge_base = await use_case.execute(knowledge_base_id)
    if not knowledge_base:
        raise NotFoundException()
    return knowledge_base


@router.patch("/{knowledge_base_id}", response_model=KnowledgeBaseRead)
async def patch_knowledge_base(
    use_case: Annotated[PatchKnowledgeBaseUseCase, Depends()],
    knowledge_base_id: UUID,
    knowledge_base_in: KnowledgeBasePatch,
):
    knowledge_base = await use_case.execute(knowledge_base_id, knowledge_base_in)
    if not knowledge_base:
        raise NotFoundException()
    return knowledge_base


@router.put("/{knowledge_base_id}", response_model=KnowledgeBaseRead)
async def put_knowledge_base(
    use_case: Annotated[PutKnowledgeBaseUseCase, Depends()],
    knowledge_base_id: UUID,
    knowledge_base_in: KnowledgeBasePut,
):
    knowledge_base = await use_case.execute(knowledge_base_id, knowledge_base_in)
    if not knowledge_base:
        raise NotFoundException()
    return knowledge_base


@router.delete("/{knowledge_base_id}", response_model=DeleteResponse)
async def delete_knowledge_base(
    use_case: Annotated[DeleteKnowledgeBaseUseCase, Depends()],
    knowledge_base_id: UUID,
):
    return await use_case.execute(knowledge_base_id)


@router.post("/{knowledge_base_id}/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_knowledge_base_document(
    knowledge_base_id: UUID,
    use_case: Annotated[IngestKnowledgeDocumentUseCase, Depends()],
    file: UploadFile = File(...),  # noqa: B008
    provider: str | None = Form(None),
):
    """Upload a document, parse it, chunk it, embed it, and index it into the vector store."""
    return await use_case.execute(knowledge_base_id=knowledge_base_id, file=file, provider=provider)


@router.get("/{knowledge_base_id}/documents", response_model=PaginatedList[KnowledgeBaseDocumentRead])
async def get_knowledge_base_documents(
    knowledge_base_id: UUID,
    doc_service: Annotated[KnowledgeBaseDocumentService, Depends()],
    pagination: PaginationParam,
):
    """List all documents and their processing status inside a specific knowledge base."""
    query_options = ListQueryOptions(
        offset=pagination.offset,
        limit=pagination.limit,
        where=(doc_service.repo.model.knowledge_base_id == knowledge_base_id,),
    )
    async with AsyncTransaction() as session:
        return await doc_service.repo.get_multi(session, query_options=query_options)


@router.post("/{knowledge_base_id}/search", response_model=KnowledgeBaseSearchResponse)
async def search_knowledge_base(
    knowledge_base_id: UUID,
    use_case: Annotated[SearchKnowledgeBaseUseCase, Depends()],
    search_request: KnowledgeBaseSearchRequest,
):
    """Retrieve similar document chunks for a query from a specific knowledge base."""
    return await use_case.execute(knowledge_base_id, search_request)
