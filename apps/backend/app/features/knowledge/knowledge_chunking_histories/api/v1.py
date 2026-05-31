from typing import Annotated
from uuid import UUID

from app.features.knowledge.knowledge_chunking_histories.schemas import (
    KnowledgeChunkingHistoryCreate,
    KnowledgeChunkingHistoryPatch,
    KnowledgeChunkingHistoryPut,
    KnowledgeChunkingHistoryRead,
)
from app.features.knowledge.knowledge_chunking_histories.usecases.crud import (
    CreateKnowledgeChunkingHistoryUseCase,
    DeleteKnowledgeChunkingHistoryUseCase,
    GetKnowledgeChunkingHistoryUseCase,
    GetMultiKnowledgeChunkingHistoryUseCase,
    PatchKnowledgeChunkingHistoryUseCase,
    PutKnowledgeChunkingHistoryUseCase,
)
from app_layer_base.base.deps.params.page import PaginationParam
from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.schemas.delete_resp import DeleteResponse
from app_layer_base.base.schemas.paginated import PaginatedList
from fastapi import APIRouter, Depends, status

router = APIRouter(prefix="/knowledge_chunking_histories", tags=["KnowledgeChunkingHistory"], dependencies=[])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=KnowledgeChunkingHistoryRead)
async def create_knowledge_chunking_history(
    use_case: Annotated[CreateKnowledgeChunkingHistoryUseCase, Depends()],
    knowledge_chunking_history_in: KnowledgeChunkingHistoryCreate,
):
    return await use_case.execute(knowledge_chunking_history_in)


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


@router.patch("/{knowledge_chunking_history_id}", response_model=KnowledgeChunkingHistoryRead)
async def patch_knowledge_chunking_history(
    use_case: Annotated[PatchKnowledgeChunkingHistoryUseCase, Depends()],
    knowledge_chunking_history_id: UUID,
    knowledge_chunking_history_in: KnowledgeChunkingHistoryPatch,
):
    knowledge_chunking_history = await use_case.execute(knowledge_chunking_history_id, knowledge_chunking_history_in)
    if not knowledge_chunking_history:
        raise NotFoundException()
    return knowledge_chunking_history


@router.put("/{knowledge_chunking_history_id}", response_model=KnowledgeChunkingHistoryRead)
async def put_knowledge_chunking_history(
    use_case: Annotated[PutKnowledgeChunkingHistoryUseCase, Depends()],
    knowledge_chunking_history_id: UUID,
    knowledge_chunking_history_in: KnowledgeChunkingHistoryPut,
):
    knowledge_chunking_history = await use_case.execute(knowledge_chunking_history_id, knowledge_chunking_history_in)
    if not knowledge_chunking_history:
        raise NotFoundException()
    return knowledge_chunking_history


@router.delete("/{knowledge_chunking_history_id}", response_model=DeleteResponse)
async def delete_knowledge_chunking_history(
    use_case: Annotated[DeleteKnowledgeChunkingHistoryUseCase, Depends()],
    knowledge_chunking_history_id: UUID,
):
    return await use_case.execute(knowledge_chunking_history_id)
