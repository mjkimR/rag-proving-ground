from typing import Annotated

from app.features.knowledge.knowledge_chunking_histories.models import KnowledgeChunkingHistory
from app.features.knowledge.knowledge_chunking_histories.schemas import (
    KnowledgeChunkingHistoryCreate,
    KnowledgeChunkingHistoryPatch,
    KnowledgeChunkingHistoryPut,
)
from app.features.knowledge.knowledge_chunking_histories.services import (
    KnowledgeChunkingHistoryContextKwargs,
    KnowledgeChunkingHistoryService,
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


class GetKnowledgeChunkingHistoryUseCase(
    BaseGetUseCase[KnowledgeChunkingHistoryService, KnowledgeChunkingHistory, KnowledgeChunkingHistoryContextKwargs]
):
    def __init__(self, service: Annotated[KnowledgeChunkingHistoryService, Depends()]) -> None:
        super().__init__(service)


class GetMultiKnowledgeChunkingHistoryUseCase(
    BaseGetMultiUseCase[
        KnowledgeChunkingHistoryService, KnowledgeChunkingHistory, KnowledgeChunkingHistoryContextKwargs
    ]
):
    def __init__(self, service: Annotated[KnowledgeChunkingHistoryService, Depends()]) -> None:
        super().__init__(service)


class CreateKnowledgeChunkingHistoryUseCase(
    BaseCreateUseCase[
        KnowledgeChunkingHistoryService,
        KnowledgeChunkingHistory,
        KnowledgeChunkingHistoryCreate,
        KnowledgeChunkingHistoryContextKwargs,
    ]
):
    def __init__(self, service: Annotated[KnowledgeChunkingHistoryService, Depends()]) -> None:
        super().__init__(service)


class PatchKnowledgeChunkingHistoryUseCase(
    BasePatchUseCase[
        KnowledgeChunkingHistoryService,
        KnowledgeChunkingHistory,
        KnowledgeChunkingHistoryPut,
        KnowledgeChunkingHistoryPatch,
        KnowledgeChunkingHistoryContextKwargs,
    ]
):
    def __init__(self, service: Annotated[KnowledgeChunkingHistoryService, Depends()]) -> None:
        super().__init__(service)


class PutKnowledgeChunkingHistoryUseCase(
    BasePutUseCase[
        KnowledgeChunkingHistoryService,
        KnowledgeChunkingHistory,
        KnowledgeChunkingHistoryPut,
        KnowledgeChunkingHistoryPatch,
        KnowledgeChunkingHistoryContextKwargs,
    ]
):
    def __init__(self, service: Annotated[KnowledgeChunkingHistoryService, Depends()]) -> None:
        super().__init__(service)


class DeleteKnowledgeChunkingHistoryUseCase(
    BaseDeleteUseCase[KnowledgeChunkingHistoryService, KnowledgeChunkingHistory, KnowledgeChunkingHistoryContextKwargs]
):
    def __init__(self, service: Annotated[KnowledgeChunkingHistoryService, Depends()]) -> None:
        super().__init__(service)
