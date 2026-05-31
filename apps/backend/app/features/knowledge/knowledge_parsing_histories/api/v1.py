from typing import Annotated
from uuid import UUID

from app.features.knowledge.knowledge_parsing_histories.schemas import (
    KnowledgeParsingHistoryCreate,
    KnowledgeParsingHistoryPatch,
    KnowledgeParsingHistoryPut,
    KnowledgeParsingHistoryRead,
)
from app.features.knowledge.knowledge_parsing_histories.usecases.crud import (
    CreateKnowledgeParsingHistoryUseCase,
    DeleteKnowledgeParsingHistoryUseCase,
    GetKnowledgeParsingHistoryUseCase,
    GetMultiKnowledgeParsingHistoryUseCase,
    PatchKnowledgeParsingHistoryUseCase,
    PutKnowledgeParsingHistoryUseCase,
)
from app_layer_base.base.deps.params.page import PaginationParam
from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.schemas.delete_resp import DeleteResponse
from app_layer_base.base.schemas.paginated import PaginatedList
from fastapi import APIRouter, Depends, status

router = APIRouter(prefix="/knowledge_parsing_histories", tags=["KnowledgeParsingHistory"], dependencies=[])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=KnowledgeParsingHistoryRead)
async def create_knowledge_parsing_history(
    use_case: Annotated[CreateKnowledgeParsingHistoryUseCase, Depends()],
    knowledge_parsing_history_in: KnowledgeParsingHistoryCreate,
):
    return await use_case.execute(knowledge_parsing_history_in)


@router.get("", response_model=PaginatedList[KnowledgeParsingHistoryRead])
async def get_knowledge_parsing_histories(
    use_case: Annotated[GetMultiKnowledgeParsingHistoryUseCase, Depends()],
    pagination: PaginationParam,
):
    query_options = ListQueryOptions(offset=pagination.offset, limit=pagination.limit)
    return await use_case.execute(query_options=query_options)


@router.get("/{knowledge_parsing_history_id}", response_model=KnowledgeParsingHistoryRead)
async def get_knowledge_parsing_history(
    use_case: Annotated[GetKnowledgeParsingHistoryUseCase, Depends()],
    knowledge_parsing_history_id: UUID,
):
    knowledge_parsing_history = await use_case.execute(knowledge_parsing_history_id)
    if not knowledge_parsing_history:
        raise NotFoundException()
    return knowledge_parsing_history


@router.patch("/{knowledge_parsing_history_id}", response_model=KnowledgeParsingHistoryRead)
async def patch_knowledge_parsing_history(
    use_case: Annotated[PatchKnowledgeParsingHistoryUseCase, Depends()],
    knowledge_parsing_history_id: UUID,
    knowledge_parsing_history_in: KnowledgeParsingHistoryPatch,
):
    knowledge_parsing_history = await use_case.execute(knowledge_parsing_history_id, knowledge_parsing_history_in)
    if not knowledge_parsing_history:
        raise NotFoundException()
    return knowledge_parsing_history


@router.put("/{knowledge_parsing_history_id}", response_model=KnowledgeParsingHistoryRead)
async def put_knowledge_parsing_history(
    use_case: Annotated[PutKnowledgeParsingHistoryUseCase, Depends()],
    knowledge_parsing_history_id: UUID,
    knowledge_parsing_history_in: KnowledgeParsingHistoryPut,
):
    knowledge_parsing_history = await use_case.execute(knowledge_parsing_history_id, knowledge_parsing_history_in)
    if not knowledge_parsing_history:
        raise NotFoundException()
    return knowledge_parsing_history


@router.delete("/{knowledge_parsing_history_id}", response_model=DeleteResponse)
async def delete_knowledge_parsing_history(
    use_case: Annotated[DeleteKnowledgeParsingHistoryUseCase, Depends()],
    knowledge_parsing_history_id: UUID,
):
    return await use_case.execute(knowledge_parsing_history_id)
