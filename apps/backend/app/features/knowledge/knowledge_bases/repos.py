from app_layer_base.base.repos.base import BaseRepository

from app.features.knowledge.knowledge_bases.models import KnowledgeBase
from app.features.knowledge.knowledge_bases.schemas import (
    KnowledgeBaseCreate,
    KnowledgeBasePatch,
    KnowledgeBasePut,
)


class KnowledgeBaseRepository(BaseRepository[KnowledgeBase, KnowledgeBaseCreate, KnowledgeBasePut, KnowledgeBasePatch]):
    model = KnowledgeBase
