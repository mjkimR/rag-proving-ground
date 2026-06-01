from typing import Annotated
from uuid import UUID

from app.features.knowledge.knowledge_embedding_histories.schemas import (
    KnowledgeEmbeddingHistoryRead,
)
from app.features.knowledge.knowledge_embedding_histories.usecases.crud import (
    GetKnowledgeEmbeddingHistoryUseCase,
    GetMultiKnowledgeEmbeddingHistoryUseCase,
)
from app_layer_base.base.deps.params.page import PaginationParam
from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.schemas.paginated import PaginatedList
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/knowledge_embedding_histories", tags=["KnowledgeEmbeddingHistory"], dependencies=[])


@router.get("", response_model=PaginatedList[KnowledgeEmbeddingHistoryRead])
async def get_knowledge_embedding_histories(
    use_case: Annotated[GetMultiKnowledgeEmbeddingHistoryUseCase, Depends()],
    pagination: PaginationParam,
):
    query_options = ListQueryOptions(offset=pagination.offset, limit=pagination.limit)
    return await use_case.execute(query_options=query_options)


@router.get("/{knowledge_embedding_history_id}", response_model=KnowledgeEmbeddingHistoryRead)
async def get_knowledge_embedding_history(
    use_case: Annotated[GetKnowledgeEmbeddingHistoryUseCase, Depends()],
    knowledge_embedding_history_id: UUID,
):
    knowledge_embedding_history = await use_case.execute(knowledge_embedding_history_id)
    if not knowledge_embedding_history:
        raise NotFoundException()
    return knowledge_embedding_history
