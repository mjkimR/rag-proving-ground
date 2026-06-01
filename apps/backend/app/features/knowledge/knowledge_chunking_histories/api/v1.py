from typing import Annotated
from uuid import UUID

from app.features.knowledge.knowledge_chunking_histories.schemas import (
    KnowledgeChunkingHistoryRead,
)
from app.features.knowledge.knowledge_chunking_histories.usecases.crud import (
    GetKnowledgeChunkingHistoryUseCase,
    GetMultiKnowledgeChunkingHistoryUseCase,
)
from app_layer_base.base.deps.params.page import PaginationParam
from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.schemas.paginated import PaginatedList
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/knowledge_chunking_histories", tags=["KnowledgeChunkingHistory"], dependencies=[])


@router.get("", response_model=PaginatedList[KnowledgeChunkingHistoryRead])
async def get_knowledge_chunking_histories(
    use_case: Annotated[GetMultiKnowledgeChunkingHistoryUseCase, Depends()],
    pagination: PaginationParam,
):
    query_options = ListQueryOptions(offset=pagination.offset, limit=pagination.limit)
    return await use_case.execute(query_options=query_options)


@router.get("/{knowledge_chunking_history_id}", response_model=KnowledgeChunkingHistoryRead)
async def get_knowledge_chunking_history(
    use_case: Annotated[GetKnowledgeChunkingHistoryUseCase, Depends()],
    knowledge_chunking_history_id: UUID,
):
    knowledge_chunking_history = await use_case.execute(knowledge_chunking_history_id)
    if not knowledge_chunking_history:
        raise NotFoundException()
    return knowledge_chunking_history
