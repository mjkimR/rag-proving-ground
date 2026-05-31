from typing import Annotated

from app.features.knowledge.knowledge_embedding_histories.models import KnowledgeEmbeddingHistory
from app.features.knowledge.knowledge_embedding_histories.schemas import (
    KnowledgeEmbeddingHistoryCreate,
    KnowledgeEmbeddingHistoryPatch,
    KnowledgeEmbeddingHistoryPut,
)
from app.features.knowledge.knowledge_embedding_histories.services import (
    KnowledgeEmbeddingHistoryContextKwargs,
    KnowledgeEmbeddingHistoryService,
)
from app_layer_base.base.usecases.crud import (
    BaseCreateUseCase,
    BaseDeleteUseCase,
    BaseGetMultiUseCase,
    BaseGetUseCase,
    BasePatchUseCase,
    BasePutUseCase,
)
from fastapi import Depends


class GetKnowledgeEmbeddingHistoryUseCase(
    BaseGetUseCase[KnowledgeEmbeddingHistoryService, KnowledgeEmbeddingHistory, KnowledgeEmbeddingHistoryContextKwargs]
):
    def __init__(self, service: Annotated[KnowledgeEmbeddingHistoryService, Depends()]) -> None:
        super().__init__(service)


class GetMultiKnowledgeEmbeddingHistoryUseCase(
    BaseGetMultiUseCase[
        KnowledgeEmbeddingHistoryService, KnowledgeEmbeddingHistory, KnowledgeEmbeddingHistoryContextKwargs
    ]
):
    def __init__(self, service: Annotated[KnowledgeEmbeddingHistoryService, Depends()]) -> None:
        super().__init__(service)


class CreateKnowledgeEmbeddingHistoryUseCase(
    BaseCreateUseCase[
        KnowledgeEmbeddingHistoryService,
        KnowledgeEmbeddingHistory,
        KnowledgeEmbeddingHistoryCreate,
        KnowledgeEmbeddingHistoryContextKwargs,
    ]
):
    def __init__(self, service: Annotated[KnowledgeEmbeddingHistoryService, Depends()]) -> None:
        super().__init__(service)


class PatchKnowledgeEmbeddingHistoryUseCase(
    BasePatchUseCase[
        KnowledgeEmbeddingHistoryService,
        KnowledgeEmbeddingHistory,
        KnowledgeEmbeddingHistoryPut,
        KnowledgeEmbeddingHistoryPatch,
        KnowledgeEmbeddingHistoryContextKwargs,
    ]
):
    def __init__(self, service: Annotated[KnowledgeEmbeddingHistoryService, Depends()]) -> None:
        super().__init__(service)


class PutKnowledgeEmbeddingHistoryUseCase(
    BasePutUseCase[
        KnowledgeEmbeddingHistoryService,
        KnowledgeEmbeddingHistory,
        KnowledgeEmbeddingHistoryPut,
        KnowledgeEmbeddingHistoryPatch,
        KnowledgeEmbeddingHistoryContextKwargs,
    ]
):
    def __init__(self, service: Annotated[KnowledgeEmbeddingHistoryService, Depends()]) -> None:
        super().__init__(service)


class DeleteKnowledgeEmbeddingHistoryUseCase(
    BaseDeleteUseCase[
        KnowledgeEmbeddingHistoryService, KnowledgeEmbeddingHistory, KnowledgeEmbeddingHistoryContextKwargs
    ]
):
    def __init__(self, service: Annotated[KnowledgeEmbeddingHistoryService, Depends()]) -> None:
        super().__init__(service)
