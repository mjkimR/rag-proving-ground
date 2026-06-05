from typing import Annotated

from app.features.knowledge.knowledge_base_pages.models import KnowledgeBasePage
from app.features.knowledge.knowledge_base_pages.repos import KnowledgeBasePageRepository
from app.features.knowledge.knowledge_base_pages.schemas import (
    KnowledgeBasePageCreate,
    KnowledgeBasePagePatch,
    KnowledgeBasePagePut,
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


class KnowledgeBasePageContextKwargs(BaseContextKwargs):
    pass


class KnowledgeBasePageService(
    BaseCreateServiceMixin[
        KnowledgeBasePageRepository, KnowledgeBasePage, KnowledgeBasePageCreate, KnowledgeBasePageContextKwargs
    ],
    BaseGetMultiServiceMixin[KnowledgeBasePageRepository, KnowledgeBasePage, KnowledgeBasePageContextKwargs],
    BaseGetServiceMixin[KnowledgeBasePageRepository, KnowledgeBasePage, KnowledgeBasePageContextKwargs],
    BaseUpdateServiceMixin[
        KnowledgeBasePageRepository,
        KnowledgeBasePage,
        KnowledgeBasePagePut,
        KnowledgeBasePagePatch,
        KnowledgeBasePageContextKwargs,
    ],
    BaseDeleteServiceMixin[KnowledgeBasePageRepository, KnowledgeBasePage, KnowledgeBasePageContextKwargs],
):
    def __init__(self, repo: Annotated[KnowledgeBasePageRepository, Depends()]):
        self._repo = repo

    @property
    def repo(self) -> KnowledgeBasePageRepository:
        return self._repo

    @property
    def context_model(self):
        return KnowledgeBasePageContextKwargs
