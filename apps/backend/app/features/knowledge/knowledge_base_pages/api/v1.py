from typing import Annotated
from uuid import UUID

from app.features.knowledge.knowledge_base_pages.query_options import get_knowledge_base_pages_query_options
from app.features.knowledge.knowledge_base_pages.schemas import (
    KnowledgeBasePageCreate,
    KnowledgeBasePagePatch,
    KnowledgeBasePagePut,
    KnowledgeBasePageRead,
)
from app.features.knowledge.knowledge_base_pages.usecases.crud import (
    CreateKnowledgeBasePageUseCase,
    DeleteKnowledgeBasePageUseCase,
    GetKnowledgeBasePageUseCase,
    GetMultiKnowledgeBasePageUseCase,
    PatchKnowledgeBasePageUseCase,
    PutKnowledgeBasePageUseCase,
)
from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.schemas.delete_resp import DeleteResponse
from app_layer_base.base.schemas.paginated import PaginatedList
from fastapi import APIRouter, Depends, status

router = APIRouter(prefix="/knowledge_base_pages", tags=["KnowledgeBasePage"], dependencies=[])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=KnowledgeBasePageRead)
async def create_knowledge_base_page(
    use_case: Annotated[CreateKnowledgeBasePageUseCase, Depends()],
    knowledge_base_page_in: KnowledgeBasePageCreate,
):
    return await use_case.execute(knowledge_base_page_in)


@router.get("", response_model=PaginatedList[KnowledgeBasePageRead])
async def get_knowledge_base_pages(
    use_case: Annotated[GetMultiKnowledgeBasePageUseCase, Depends()],
    query_options: Annotated[ListQueryOptions, Depends(get_knowledge_base_pages_query_options)],
):
    return await use_case.execute(query_options=query_options)


@router.get("/{knowledge_base_page_id}", response_model=KnowledgeBasePageRead)
async def get_knowledge_base_page(
    use_case: Annotated[GetKnowledgeBasePageUseCase, Depends()],
    knowledge_base_page_id: UUID,
):
    knowledge_base_page = await use_case.execute(knowledge_base_page_id)
    if not knowledge_base_page:
        raise NotFoundException()
    return knowledge_base_page


@router.patch("/{knowledge_base_page_id}", response_model=KnowledgeBasePageRead)
async def patch_knowledge_base_page(
    use_case: Annotated[PatchKnowledgeBasePageUseCase, Depends()],
    knowledge_base_page_id: UUID,
    knowledge_base_page_in: KnowledgeBasePagePatch,
):
    knowledge_base_page = await use_case.execute(knowledge_base_page_id, knowledge_base_page_in)
    if not knowledge_base_page:
        raise NotFoundException()
    return knowledge_base_page


@router.put("/{knowledge_base_page_id}", response_model=KnowledgeBasePageRead)
async def put_knowledge_base_page(
    use_case: Annotated[PutKnowledgeBasePageUseCase, Depends()],
    knowledge_base_page_id: UUID,
    knowledge_base_page_in: KnowledgeBasePagePut,
):
    knowledge_base_page = await use_case.execute(knowledge_base_page_id, knowledge_base_page_in)
    if not knowledge_base_page:
        raise NotFoundException()
    return knowledge_base_page


@router.delete("/{knowledge_base_page_id}", response_model=DeleteResponse)
async def delete_knowledge_base_page(
    use_case: Annotated[DeleteKnowledgeBasePageUseCase, Depends()],
    knowledge_base_page_id: UUID,
):
    return await use_case.execute(knowledge_base_page_id)
