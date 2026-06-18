from typing import Annotated

from app.features.knowledge.synonyms.models import SynonymMap
from app.features.knowledge.synonyms.repos import SynonymMapRepository
from app.features.knowledge.synonyms.schemas import SynonymMapCreate, SynonymMapPatch, SynonymMapPut
from app_layer_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
    BaseUpdateServiceMixin,
)
from fastapi import Depends


class SynonymContextKwargs(BaseContextKwargs):
    pass


class SynonymMapService(
    BaseCreateServiceMixin[SynonymMapRepository, SynonymMap, SynonymMapCreate, SynonymContextKwargs],
    BaseGetMultiServiceMixin[SynonymMapRepository, SynonymMap, SynonymContextKwargs],
    BaseGetServiceMixin[SynonymMapRepository, SynonymMap, SynonymContextKwargs],
    BaseUpdateServiceMixin[SynonymMapRepository, SynonymMap, SynonymMapPut, SynonymMapPatch, SynonymContextKwargs],
    BaseDeleteServiceMixin[SynonymMapRepository, SynonymMap, SynonymContextKwargs],
):
    def __init__(self, repo: Annotated[SynonymMapRepository, Depends()]):
        self._repo = repo

    @property
    def repo(self) -> SynonymMapRepository:
        return self._repo

    @property
    def context_model(self):
        return SynonymContextKwargs
