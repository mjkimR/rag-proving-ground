from typing import Annotated

from app.features.knowledge.knowledge_parsing_histories.models import KnowledgeParsingHistory
from app.features.knowledge.knowledge_parsing_histories.repos import KnowledgeParsingHistoryRepository
from app.features.knowledge.knowledge_parsing_histories.schemas import (
    KnowledgeParsingHistoryCreate,
    KnowledgeParsingHistoryPatch,
    KnowledgeParsingHistoryPut,
)
from app_layer_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
    BaseUpdateServiceMixin,
)
from fastapi import Depends


class KnowledgeParsingHistoryContextKwargs(BaseContextKwargs):
    pass


class KnowledgeParsingHistoryService(
    BaseCreateServiceMixin[
        KnowledgeParsingHistoryRepository,
        KnowledgeParsingHistory,
        KnowledgeParsingHistoryCreate,
        KnowledgeParsingHistoryContextKwargs,
    ],
    BaseGetMultiServiceMixin[
        KnowledgeParsingHistoryRepository, KnowledgeParsingHistory, KnowledgeParsingHistoryContextKwargs
    ],
    BaseGetServiceMixin[
        KnowledgeParsingHistoryRepository, KnowledgeParsingHistory, KnowledgeParsingHistoryContextKwargs
    ],
    BaseUpdateServiceMixin[
        KnowledgeParsingHistoryRepository,
        KnowledgeParsingHistory,
        KnowledgeParsingHistoryPut,
        KnowledgeParsingHistoryPatch,
        KnowledgeParsingHistoryContextKwargs,
    ],
    BaseDeleteServiceMixin[
        KnowledgeParsingHistoryRepository, KnowledgeParsingHistory, KnowledgeParsingHistoryContextKwargs
    ],
):
    def __init__(self, repo: Annotated[KnowledgeParsingHistoryRepository, Depends()]):
        self._repo = repo

    @property
    def repo(self) -> KnowledgeParsingHistoryRepository:
        return self._repo

    @property
    def context_model(self):
        return KnowledgeParsingHistoryContextKwargs
