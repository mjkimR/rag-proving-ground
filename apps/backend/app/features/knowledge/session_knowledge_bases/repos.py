from app_layer_base.base.repos.base import BaseRepository

from app.features.knowledge.session_knowledge_bases.models import SessionKnowledgeBase
from app.features.knowledge.session_knowledge_bases.schemas import (
    SessionKnowledgeBaseCreate,
    SessionKnowledgeBasePatch,
    SessionKnowledgeBasePut,
)


class SessionKnowledgeBaseRepository(
    BaseRepository[SessionKnowledgeBase, SessionKnowledgeBaseCreate, SessionKnowledgeBasePut, SessionKnowledgeBasePatch]
):
    model = SessionKnowledgeBase
