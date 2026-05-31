from typing import Annotated

from app.features.knowledge.knowledge_parsing_histories.models import KnowledgeParsingHistory
from app.features.knowledge.knowledge_parsing_histories.schemas import (
    KnowledgeParsingHistoryCreate,
    KnowledgeParsingHistoryPatch,
    KnowledgeParsingHistoryPut,
)
from app.features.knowledge.knowledge_parsing_histories.services import (
    KnowledgeParsingHistoryContextKwargs,
    KnowledgeParsingHistoryService,
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


class GetKnowledgeParsingHistoryUseCase(
    BaseGetUseCase[KnowledgeParsingHistoryService, KnowledgeParsingHistory, KnowledgeParsingHistoryContextKwargs]
):
    def __init__(self, service: Annotated[KnowledgeParsingHistoryService, Depends()]) -> None:
        super().__init__(service)


class GetMultiKnowledgeParsingHistoryUseCase(
    BaseGetMultiUseCase[KnowledgeParsingHistoryService, KnowledgeParsingHistory, KnowledgeParsingHistoryContextKwargs]
):
    def __init__(self, service: Annotated[KnowledgeParsingHistoryService, Depends()]) -> None:
        super().__init__(service)


class CreateKnowledgeParsingHistoryUseCase(
    BaseCreateUseCase[
        KnowledgeParsingHistoryService,
        KnowledgeParsingHistory,
        KnowledgeParsingHistoryCreate,
        KnowledgeParsingHistoryContextKwargs,
    ]
):
    def __init__(self, service: Annotated[KnowledgeParsingHistoryService, Depends()]) -> None:
        super().__init__(service)


class PatchKnowledgeParsingHistoryUseCase(
    BasePatchUseCase[
        KnowledgeParsingHistoryService,
        KnowledgeParsingHistory,
        KnowledgeParsingHistoryPut,
        KnowledgeParsingHistoryPatch,
        KnowledgeParsingHistoryContextKwargs,
    ]
):
    def __init__(self, service: Annotated[KnowledgeParsingHistoryService, Depends()]) -> None:
        super().__init__(service)


class PutKnowledgeParsingHistoryUseCase(
    BasePutUseCase[
        KnowledgeParsingHistoryService,
        KnowledgeParsingHistory,
        KnowledgeParsingHistoryPut,
        KnowledgeParsingHistoryPatch,
        KnowledgeParsingHistoryContextKwargs,
    ]
):
    def __init__(self, service: Annotated[KnowledgeParsingHistoryService, Depends()]) -> None:
        super().__init__(service)


class DeleteKnowledgeParsingHistoryUseCase(
    BaseDeleteUseCase[KnowledgeParsingHistoryService, KnowledgeParsingHistory, KnowledgeParsingHistoryContextKwargs]
):
    def __init__(self, service: Annotated[KnowledgeParsingHistoryService, Depends()]) -> None:
        super().__init__(service)
