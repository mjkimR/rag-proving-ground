from app.features.knowledge.knowledge_base_documents.models import KnowledgeBaseDocument
from app.features.knowledge.knowledge_base_documents.schemas import (
    KnowledgeBaseDocumentCreate,
    KnowledgeBaseDocumentPatch,
    KnowledgeBaseDocumentPut,
)
from app_layer_base.base.repos.base import BaseRepository


class KnowledgeBaseDocumentRepository(
    BaseRepository[
        KnowledgeBaseDocument, KnowledgeBaseDocumentCreate, KnowledgeBaseDocumentPut, KnowledgeBaseDocumentPatch
    ]
):
    model = KnowledgeBaseDocument
