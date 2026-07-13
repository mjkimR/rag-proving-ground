from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from app_layer_base.base.repos.base import PrimaryKeyType
from app_layer_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
    BaseUpdateServiceMixin,
)
from app_layer_base.base.services.hooks import CreateHook, Operation, UpdateHook
from fastapi import Depends
from pydantic import BaseModel

from app.features.providers.ai_models.models import AIModel
from app.features.providers.ai_models.repos import AIModelRepository
from app.features.providers.ai_models.schemas import AIModelCreate, AIModelPatch, AIModelPut


class AIModelContextKwargs(BaseContextKwargs):
    pass


class AIModelDefaultFlagHook(
    CreateHook[AIModel, AIModelContextKwargs],
    UpdateHook[AIModel, AIModelContextKwargs],
):
    """Keeps at most one default model per model_type.

    Writing ``is_default=True`` clears the previous default of that type first,
    on every write path through the service.
    """

    def __init__(self, repo: AIModelRepository):
        self.repo = repo

    @asynccontextmanager
    async def create_context(self, op: Operation[AIModelContextKwargs], data: BaseModel) -> AsyncIterator[None]:
        if getattr(data, "is_default", False):
            model_type = getattr(data, "model_type", None)
            if model_type:
                await self.repo.clear_default(op.session, model_type)
        yield

    @asynccontextmanager
    async def update_context(
        self,
        op: Operation[AIModelContextKwargs],
        pk: PrimaryKeyType,
        data: BaseModel,
        partial: bool = True,
    ) -> AsyncIterator[None]:
        if getattr(data, "is_default", None):
            model_type = getattr(data, "model_type", None)
            if not model_type:
                # A partial update may omit model_type; read it from the stored row.
                current = await self.repo.get_by_pk(op.session, pk)
                model_type = current.model_type if current else None
            if model_type:
                await self.repo.clear_default(op.session, model_type)
        yield


class AIModelService(
    BaseCreateServiceMixin[AIModelRepository, AIModel, AIModelCreate, AIModelContextKwargs],
    BaseGetMultiServiceMixin[AIModelRepository, AIModel, AIModelContextKwargs],
    BaseGetServiceMixin[AIModelRepository, AIModel, AIModelContextKwargs],
    BaseUpdateServiceMixin[AIModelRepository, AIModel, AIModelPut, AIModelPatch, AIModelContextKwargs],
    BaseDeleteServiceMixin[AIModelRepository, AIModel, AIModelContextKwargs],
):
    def __init__(self, repo: Annotated[AIModelRepository, Depends()]):
        self._repo = repo
        self.hooks = (AIModelDefaultFlagHook(repo),)

    @property
    def repo(self) -> AIModelRepository:
        return self._repo

    @property
    def context_model(self):
        return AIModelContextKwargs
