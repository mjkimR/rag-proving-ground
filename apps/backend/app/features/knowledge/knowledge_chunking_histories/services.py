from typing import Annotated

from app.features.knowledge.knowledge_chunking_histories.models import KnowledgeChunkingHistory
from app.features.knowledge.knowledge_chunking_histories.repos import KnowledgeChunkingHistoryRepository
from app.features.knowledge.knowledge_chunking_histories.schemas import (
    KnowledgeChunkingHistoryCreate,
    KnowledgeChunkingHistoryPatch,
    KnowledgeChunkingHistoryPut,
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


class KnowledgeChunkingHistoryContextKwargs(BaseContextKwargs):
    pass


class KnowledgeChunkingHistoryService(
    BaseCreateServiceMixin[
        KnowledgeChunkingHistoryRepository,
        KnowledgeChunkingHistory,
        KnowledgeChunkingHistoryCreate,
        KnowledgeChunkingHistoryContextKwargs,
    ],
    BaseGetMultiServiceMixin[
        KnowledgeChunkingHistoryRepository, KnowledgeChunkingHistory, KnowledgeChunkingHistoryContextKwargs
    ],
    BaseGetServiceMixin[
        KnowledgeChunkingHistoryRepository, KnowledgeChunkingHistory, KnowledgeChunkingHistoryContextKwargs
    ],
    BaseUpdateServiceMixin[
        KnowledgeChunkingHistoryRepository,
        KnowledgeChunkingHistory,
        KnowledgeChunkingHistoryPut,
        KnowledgeChunkingHistoryPatch,
        KnowledgeChunkingHistoryContextKwargs,
    ],
    BaseDeleteServiceMixin[
        KnowledgeChunkingHistoryRepository, KnowledgeChunkingHistory, KnowledgeChunkingHistoryContextKwargs
    ],
):
    def __init__(self, repo: Annotated[KnowledgeChunkingHistoryRepository, Depends()]):
        self._repo = repo

    @property
    def repo(self) -> KnowledgeChunkingHistoryRepository:
        return self._repo

    @property
    def context_model(self):
        return KnowledgeChunkingHistoryContextKwargs
