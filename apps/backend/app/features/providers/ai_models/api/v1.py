from typing import Annotated
from uuid import UUID

from app.features.providers.ai_models.schemas import AIModelCreate, AIModelPatch, AIModelPut, AIModelRead
from app.features.providers.ai_models.usecases.crud import (
    CreateAIModelUseCase,
    DeleteAIModelUseCase,
    GetAIModelUseCase,
    GetMultiAIModelUseCase,
    PatchAIModelUseCase,
    PutAIModelUseCase,
)
from app.features.providers.ai_models.usecases.sync import SyncAIModelsUseCase
from app.features.providers.ai_models.usecases.test import TestAIModelConnectionUseCase
from app_layer_base.base.deps.params.page import PaginationParam
from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.schemas.delete_resp import DeleteResponse
from app_layer_base.base.schemas.paginated import PaginatedList
from fastapi import APIRouter, Depends, status

router = APIRouter(prefix="/ai_models", tags=["AIModel"], dependencies=[])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AIModelRead)
async def create_ai_model(
    use_case: Annotated[CreateAIModelUseCase, Depends()],
    ai_model_in: AIModelCreate,
):
    return await use_case.execute(ai_model_in)


@router.get("", response_model=PaginatedList[AIModelRead])
async def get_ai_models(
    use_case: Annotated[GetMultiAIModelUseCase, Depends()],
    pagination: PaginationParam,
):
    query_options = ListQueryOptions(offset=pagination.offset, limit=pagination.limit)
    return await use_case.execute(query_options=query_options)


@router.get("/{ai_model_id}", response_model=AIModelRead)
async def get_ai_model(
    use_case: Annotated[GetAIModelUseCase, Depends()],
    ai_model_id: UUID,
):
    ai_model = await use_case.execute(ai_model_id)
    if not ai_model:
        raise NotFoundException()
    return ai_model


@router.patch("/{ai_model_id}", response_model=AIModelRead)
async def patch_ai_model(
    use_case: Annotated[PatchAIModelUseCase, Depends()],
    ai_model_id: UUID,
    ai_model_in: AIModelPatch,
):
    ai_model = await use_case.execute(ai_model_id, ai_model_in)
    if not ai_model:
        raise NotFoundException()
    return ai_model


@router.put("/{ai_model_id}", response_model=AIModelRead)
async def put_ai_model(
    use_case: Annotated[PutAIModelUseCase, Depends()],
    ai_model_id: UUID,
    ai_model_in: AIModelPut,
):
    ai_model = await use_case.execute(ai_model_id, ai_model_in)
    if not ai_model:
        raise NotFoundException()
    return ai_model


@router.delete("/{ai_model_id}", response_model=DeleteResponse)
async def delete_ai_model(
    use_case: Annotated[DeleteAIModelUseCase, Depends()],
    ai_model_id: UUID,
):
    return await use_case.execute(ai_model_id)


@router.post("/sync", response_model=list[AIModelRead])
async def sync_ai_models(
    use_case: Annotated[SyncAIModelsUseCase, Depends()],
):
    return await use_case.execute()


@router.post("/{ai_model_id}/test")
async def test_ai_model(
    use_case: Annotated[TestAIModelConnectionUseCase, Depends()],
    ai_model_id: UUID,
):
    return await use_case.execute(ai_model_id)
