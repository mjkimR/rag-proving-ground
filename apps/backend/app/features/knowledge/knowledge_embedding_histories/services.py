from typing import Annotated

from app.features.knowledge.knowledge_embedding_histories.models import KnowledgeEmbeddingHistory
from app.features.knowledge.knowledge_embedding_histories.repos import KnowledgeEmbeddingHistoryRepository
from app.features.knowledge.knowledge_embedding_histories.schemas import (
    KnowledgeEmbeddingHistoryCreate,
    KnowledgeEmbeddingHistoryPatch,
    KnowledgeEmbeddingHistoryPut,
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


class KnowledgeEmbeddingHistoryContextKwargs(BaseContextKwargs):
    pass


class KnowledgeEmbeddingHistoryService(
    BaseCreateServiceMixin[
        KnowledgeEmbeddingHistoryRepository,
        KnowledgeEmbeddingHistory,
        KnowledgeEmbeddingHistoryCreate,
        KnowledgeEmbeddingHistoryContextKwargs,
    ],
    BaseGetMultiServiceMixin[
        KnowledgeEmbeddingHistoryRepository, KnowledgeEmbeddingHistory, KnowledgeEmbeddingHistoryContextKwargs
    ],
    BaseGetServiceMixin[
        KnowledgeEmbeddingHistoryRepository, KnowledgeEmbeddingHistory, KnowledgeEmbeddingHistoryContextKwargs
    ],
    BaseUpdateServiceMixin[
        KnowledgeEmbeddingHistoryRepository,
        KnowledgeEmbeddingHistory,
        KnowledgeEmbeddingHistoryPut,
        KnowledgeEmbeddingHistoryPatch,
        KnowledgeEmbeddingHistoryContextKwargs,
    ],
    BaseDeleteServiceMixin[
        KnowledgeEmbeddingHistoryRepository, KnowledgeEmbeddingHistory, KnowledgeEmbeddingHistoryContextKwargs
    ],
):
    def __init__(self, repo: Annotated[KnowledgeEmbeddingHistoryRepository, Depends()]):
        self._repo = repo

    @property
    def repo(self) -> KnowledgeEmbeddingHistoryRepository:
        return self._repo

    @property
    def context_model(self):
        return KnowledgeEmbeddingHistoryContextKwargs
