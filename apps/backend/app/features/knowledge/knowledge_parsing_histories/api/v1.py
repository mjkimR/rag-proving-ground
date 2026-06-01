from typing import Annotated
from uuid import UUID

from app.features.knowledge.knowledge_parsing_histories.schemas import (
    KnowledgeParsingHistoryRead,
)
from app.features.knowledge.knowledge_parsing_histories.usecases.crud import (
    GetKnowledgeParsingHistoryUseCase,
    GetMultiKnowledgeParsingHistoryUseCase,
)
from app_layer_base.base.deps.params.page import PaginationParam
from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.schemas.paginated import PaginatedList
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/knowledge_parsing_histories", tags=["KnowledgeParsingHistory"], dependencies=[])


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
