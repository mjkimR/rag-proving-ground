from typing import Annotated

from app.features.knowledge.session_knowledge_bases.models import SessionKnowledgeBase
from app.features.knowledge.session_knowledge_bases.repos import SessionKnowledgeBaseRepository
from app.features.knowledge.session_knowledge_bases.schemas import (
    SessionKnowledgeBaseCreate,
    SessionKnowledgeBasePatch,
    SessionKnowledgeBasePut,
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


class SessionKnowledgeBaseContextKwargs(BaseContextKwargs):
    pass


class SessionKnowledgeBaseService(
    BaseCreateServiceMixin[
        SessionKnowledgeBaseRepository,
        SessionKnowledgeBase,
        SessionKnowledgeBaseCreate,
        SessionKnowledgeBaseContextKwargs,
    ],
    BaseGetMultiServiceMixin[SessionKnowledgeBaseRepository, SessionKnowledgeBase, SessionKnowledgeBaseContextKwargs],
    BaseGetServiceMixin[SessionKnowledgeBaseRepository, SessionKnowledgeBase, SessionKnowledgeBaseContextKwargs],
    BaseUpdateServiceMixin[
        SessionKnowledgeBaseRepository,
        SessionKnowledgeBase,
        SessionKnowledgeBasePut,
        SessionKnowledgeBasePatch,
        SessionKnowledgeBaseContextKwargs,
    ],
    BaseDeleteServiceMixin[SessionKnowledgeBaseRepository, SessionKnowledgeBase, SessionKnowledgeBaseContextKwargs],
):
    def __init__(self, repo: Annotated[SessionKnowledgeBaseRepository, Depends()]):
        self._repo = repo

    @property
    def repo(self) -> SessionKnowledgeBaseRepository:
        return self._repo

    @property
    def context_model(self):
        return SessionKnowledgeBaseContextKwargs
