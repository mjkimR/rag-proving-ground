from typing import Annotated

from app_layer_base.base.usecases.crud import (
    BaseCreateUseCase,
    BaseDeleteUseCase,
    BaseGetMultiUseCase,
    BaseGetUseCase,
    BasePatchUseCase,
    BasePutUseCase,
)
from fastapi import Depends

from app.features.knowledge.knowledge_base_pages.models import KnowledgeBasePage
from app.features.knowledge.knowledge_base_pages.schemas import (
    KnowledgeBasePageCreate,
    KnowledgeBasePagePatch,
    KnowledgeBasePagePut,
)
from app.features.knowledge.knowledge_base_pages.services import (
    KnowledgeBasePageContextKwargs,
    KnowledgeBasePageService,
)


class GetKnowledgeBasePageUseCase(
    BaseGetUseCase[KnowledgeBasePageService, KnowledgeBasePage, KnowledgeBasePageContextKwargs]
):
    def __init__(self, service: Annotated[KnowledgeBasePageService, Depends()]) -> None:
        super().__init__(service)


class GetMultiKnowledgeBasePageUseCase(
    BaseGetMultiUseCase[KnowledgeBasePageService, KnowledgeBasePage, KnowledgeBasePageContextKwargs]
):
    def __init__(self, service: Annotated[KnowledgeBasePageService, Depends()]) -> None:
        super().__init__(service)


class CreateKnowledgeBasePageUseCase(
    BaseCreateUseCase[
        KnowledgeBasePageService, KnowledgeBasePage, KnowledgeBasePageCreate, KnowledgeBasePageContextKwargs
    ]
):
    def __init__(self, service: Annotated[KnowledgeBasePageService, Depends()]) -> None:
        super().__init__(service)


class PatchKnowledgeBasePageUseCase(
    BasePatchUseCase[
        KnowledgeBasePageService,
        KnowledgeBasePage,
        KnowledgeBasePagePut,
        KnowledgeBasePagePatch,
        KnowledgeBasePageContextKwargs,
    ]
):
    def __init__(self, service: Annotated[KnowledgeBasePageService, Depends()]) -> None:
        super().__init__(service)


class PutKnowledgeBasePageUseCase(
    BasePutUseCase[
        KnowledgeBasePageService,
        KnowledgeBasePage,
        KnowledgeBasePagePut,
        KnowledgeBasePagePatch,
        KnowledgeBasePageContextKwargs,
    ]
):
    def __init__(self, service: Annotated[KnowledgeBasePageService, Depends()]) -> None:
        super().__init__(service)


class DeleteKnowledgeBasePageUseCase(
    BaseDeleteUseCase[KnowledgeBasePageService, KnowledgeBasePage, KnowledgeBasePageContextKwargs]
):
    def __init__(self, service: Annotated[KnowledgeBasePageService, Depends()]) -> None:
        super().__init__(service)
