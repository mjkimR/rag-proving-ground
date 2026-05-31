from typing import Annotated
from uuid import UUID

from app.features.knowledge.knowledge_embedding_histories.schemas import (
    KnowledgeEmbeddingHistoryCreate,
    KnowledgeEmbeddingHistoryPatch,
    KnowledgeEmbeddingHistoryPut,
    KnowledgeEmbeddingHistoryRead,
)
from app.features.knowledge.knowledge_embedding_histories.usecases.crud import (
    CreateKnowledgeEmbeddingHistoryUseCase,
    DeleteKnowledgeEmbeddingHistoryUseCase,
    GetKnowledgeEmbeddingHistoryUseCase,
    GetMultiKnowledgeEmbeddingHistoryUseCase,
    PatchKnowledgeEmbeddingHistoryUseCase,
    PutKnowledgeEmbeddingHistoryUseCase,
)
from app_layer_base.base.deps.params.page import PaginationParam
from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.schemas.delete_resp import DeleteResponse
from app_layer_base.base.schemas.paginated import PaginatedList
from fastapi import APIRouter, Depends, status

router = APIRouter(prefix="/knowledge_embedding_histories", tags=["KnowledgeEmbeddingHistory"], dependencies=[])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=KnowledgeEmbeddingHistoryRead)
async def create_knowledge_embedding_history(
    use_case: Annotated[CreateKnowledgeEmbeddingHistoryUseCase, Depends()],
    knowledge_embedding_history_in: KnowledgeEmbeddingHistoryCreate,
):
    return await use_case.execute(knowledge_embedding_history_in)


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


@router.patch("/{knowledge_embedding_history_id}", response_model=KnowledgeEmbeddingHistoryRead)
async def patch_knowledge_embedding_history(
    use_case: Annotated[PatchKnowledgeEmbeddingHistoryUseCase, Depends()],
    knowledge_embedding_history_id: UUID,
    knowledge_embedding_history_in: KnowledgeEmbeddingHistoryPatch,
):
    knowledge_embedding_history = await use_case.execute(knowledge_embedding_history_id, knowledge_embedding_history_in)
    if not knowledge_embedding_history:
        raise NotFoundException()
    return knowledge_embedding_history


@router.put("/{knowledge_embedding_history_id}", response_model=KnowledgeEmbeddingHistoryRead)
async def put_knowledge_embedding_history(
    use_case: Annotated[PutKnowledgeEmbeddingHistoryUseCase, Depends()],
    knowledge_embedding_history_id: UUID,
    knowledge_embedding_history_in: KnowledgeEmbeddingHistoryPut,
):
    knowledge_embedding_history = await use_case.execute(knowledge_embedding_history_id, knowledge_embedding_history_in)
    if not knowledge_embedding_history:
        raise NotFoundException()
    return knowledge_embedding_history


@router.delete("/{knowledge_embedding_history_id}", response_model=DeleteResponse)
async def delete_knowledge_embedding_history(
    use_case: Annotated[DeleteKnowledgeEmbeddingHistoryUseCase, Depends()],
    knowledge_embedding_history_id: UUID,
):
    return await use_case.execute(knowledge_embedding_history_id)
