from typing import Annotated, Any

from app_layer_base.base.repos.base import PrimaryKeyType
from app_layer_base.base.usecases.crud import (
    BaseCreateUseCase,
    BaseDeleteUseCase,
    BaseGetMultiUseCase,
    BaseGetUseCase,
    BasePatchUseCase,
    BasePutUseCase,
)
from fastapi import Depends
from sqlalchemy import update
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

    async def _execute(
        self,
        session: AsyncSession,
        obj_data: AIModelCreate,
        context: AIModelContextKwargs | None,
    ) -> AIModel:
        if obj_data.is_default:
            await session.execute(
                update(AIModel).where(AIModel.model_type == obj_data.model_type).values(is_default=False)
            )
        created = await super()._execute(session, obj_data, context)
        await refresh_ai_models_cache(session)
        return created


class PatchAIModelUseCase(BasePatchUseCase[AIModelService, AIModel, AIModelPut, AIModelPatch, AIModelContextKwargs]):
    def __init__(self, service: Annotated[AIModelService, Depends()]) -> None:
        super().__init__(service)

    async def _execute(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: AIModelPatch,
        context: AIModelContextKwargs | None,
    ) -> AIModel | None:
        if obj_data.is_default:
            model = await self.service.repo.get_by_pk(session, obj_pk)
            if model:
                model_type = obj_data.model_type or model.model_type
                await session.execute(update(AIModel).where(AIModel.model_type == model_type).values(is_default=False))
        updated = await super()._execute(session, obj_pk, obj_data, context)
        await refresh_ai_models_cache(session)
        return updated


class PutAIModelUseCase(BasePutUseCase[AIModelService, AIModel, AIModelPut, AIModelPatch, AIModelContextKwargs]):
    def __init__(self, service: Annotated[AIModelService, Depends()]) -> None:
        super().__init__(service)

    async def _execute(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: AIModelPut,
        context: AIModelContextKwargs | None,
    ) -> AIModel | None:
        if obj_data.is_default:
            await session.execute(
                update(AIModel).where(AIModel.model_type == obj_data.model_type).values(is_default=False)
            )
        updated = await super()._execute(session, obj_pk, obj_data, context)
        await refresh_ai_models_cache(session)
        return updated


class DeleteAIModelUseCase(BaseDeleteUseCase[AIModelService, AIModel, AIModelContextKwargs]):
    def __init__(self, service: Annotated[AIModelService, Depends()]) -> None:
        super().__init__(service)

    async def _execute(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        context: AIModelContextKwargs | None,
    ) -> Any:
        deleted = await super()._execute(session, obj_pk, context)
        await refresh_ai_models_cache(session)
        return deleted
