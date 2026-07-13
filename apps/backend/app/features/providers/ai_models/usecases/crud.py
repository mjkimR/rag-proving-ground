from typing import Annotated

from app_layer_base.base.schemas.delete_resp import DeleteResponse
from app_layer_base.base.usecases.crud import (
    BaseCreateUseCase,
    BaseDeleteUseCase,
    BaseGetMultiUseCase,
    BaseGetUseCase,
    BasePatchUseCase,
    BasePutUseCase,
)
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.providers.ai_models.models import AIModel
from app.features.providers.ai_models.schemas import AIModelCreate, AIModelPatch, AIModelPut
from app.features.providers.ai_models.services import AIModelContextKwargs, AIModelService
from app.features.providers.routes.cache import refresh_ai_models_cache


class GetAIModelUseCase(BaseGetUseCase[AIModelService, AIModel, AIModelContextKwargs]):
    def __init__(self, service: Annotated[AIModelService, Depends()]) -> None:
        super().__init__(service)


class GetMultiAIModelUseCase(BaseGetMultiUseCase[AIModelService, AIModel, AIModelContextKwargs]):
    def __init__(self, service: Annotated[AIModelService, Depends()]) -> None:
        super().__init__(service)


class CreateAIModelUseCase(BaseCreateUseCase[AIModelService, AIModel, AIModelCreate, AIModelContextKwargs]):
    def __init__(self, service: Annotated[AIModelService, Depends()]) -> None:
        super().__init__(service)

    async def _post_execute(
        self,
        session: AsyncSession,
        obj: AIModel,
        obj_data: AIModelCreate,
        context: AIModelContextKwargs | None,
    ) -> AIModel:
        await refresh_ai_models_cache(session)
        return obj


class PatchAIModelUseCase(BasePatchUseCase[AIModelService, AIModel, AIModelPut, AIModelPatch, AIModelContextKwargs]):
    def __init__(self, service: Annotated[AIModelService, Depends()]) -> None:
        super().__init__(service)

    async def _post_execute(
        self,
        session: AsyncSession,
        obj: AIModel | None,
        obj_data: AIModelPut | AIModelPatch,
        context: AIModelContextKwargs | None,
    ) -> AIModel | None:
        await refresh_ai_models_cache(session)
        return obj


class PutAIModelUseCase(BasePutUseCase[AIModelService, AIModel, AIModelPut, AIModelPatch, AIModelContextKwargs]):
    def __init__(self, service: Annotated[AIModelService, Depends()]) -> None:
        super().__init__(service)

    async def _post_execute(
        self,
        session: AsyncSession,
        obj: AIModel | None,
        obj_data: AIModelPut | AIModelPatch,
        context: AIModelContextKwargs | None,
    ) -> AIModel | None:
        await refresh_ai_models_cache(session)
        return obj


class DeleteAIModelUseCase(BaseDeleteUseCase[AIModelService, AIModel, AIModelContextKwargs]):
    def __init__(self, service: Annotated[AIModelService, Depends()]) -> None:
        super().__init__(service)

    async def _post_execute(
        self,
        session: AsyncSession,
        obj: DeleteResponse,
        context: AIModelContextKwargs | None,
    ) -> DeleteResponse:
        await refresh_ai_models_cache(session)
        return obj
