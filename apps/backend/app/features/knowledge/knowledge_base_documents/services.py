from typing import Annotated

from app.features.knowledge.knowledge_base_documents.models import KnowledgeBaseDocument
from app.features.knowledge.knowledge_base_documents.repos import KnowledgeBaseDocumentRepository
from app.features.knowledge.knowledge_base_documents.schemas import (
    KnowledgeBaseDocumentCreate,
    KnowledgeBaseDocumentPatch,
    KnowledgeBaseDocumentPut,
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


class KnowledgeBaseDocumentContextKwargs(BaseContextKwargs):
    pass


class KnowledgeBaseDocumentService(
    BaseCreateServiceMixin[
        KnowledgeBaseDocumentRepository,
        KnowledgeBaseDocument,
        KnowledgeBaseDocumentCreate,
        KnowledgeBaseDocumentContextKwargs,
    ],
    BaseGetMultiServiceMixin[
        KnowledgeBaseDocumentRepository, KnowledgeBaseDocument, KnowledgeBaseDocumentContextKwargs
    ],
    BaseGetServiceMixin[KnowledgeBaseDocumentRepository, KnowledgeBaseDocument, KnowledgeBaseDocumentContextKwargs],
    BaseUpdateServiceMixin[
        KnowledgeBaseDocumentRepository,
        KnowledgeBaseDocument,
        KnowledgeBaseDocumentPut,
        KnowledgeBaseDocumentPatch,
        KnowledgeBaseDocumentContextKwargs,
    ],
    BaseDeleteServiceMixin[KnowledgeBaseDocumentRepository, KnowledgeBaseDocument, KnowledgeBaseDocumentContextKwargs],
):
    def __init__(self, repo: Annotated[KnowledgeBaseDocumentRepository, Depends()]):
        self._repo = repo

    @property
    def repo(self) -> KnowledgeBaseDocumentRepository:
        return self._repo

    @property
    def context_model(self):
        return KnowledgeBaseDocumentContextKwargs
