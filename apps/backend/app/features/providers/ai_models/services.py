from typing import Annotated

from app.features.providers.ai_models.models import AIModel
from app.features.providers.ai_models.repos import AIModelRepository
from app.features.providers.ai_models.schemas import AIModelCreate, AIModelPatch, AIModelPut
from app_layer_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
    BaseUpdateServiceMixin,
)
from fastapi import Depends


class AIModelContextKwargs(BaseContextKwargs):
    pass


class AIModelService(
    BaseCreateServiceMixin[AIModelRepository, AIModel, AIModelCreate, AIModelContextKwargs],
    BaseGetMultiServiceMixin[AIModelRepository, AIModel, AIModelContextKwargs],
    BaseGetServiceMixin[AIModelRepository, AIModel, AIModelContextKwargs],
    BaseUpdateServiceMixin[AIModelRepository, AIModel, AIModelPut, AIModelPatch, AIModelContextKwargs],
    BaseDeleteServiceMixin[AIModelRepository, AIModel, AIModelContextKwargs],
):
    def __init__(self, repo: Annotated[AIModelRepository, Depends()]):
        self._repo = repo

    @property
    def repo(self) -> AIModelRepository:
        return self._repo

    @property
    def context_model(self):
        return AIModelContextKwargs
