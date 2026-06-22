from app.features.knowledge.session_knowledge_bases.models import SessionKnowledgeBase
from app.features.knowledge.session_knowledge_bases.schemas import (
    SessionKnowledgeBaseCreate,
    SessionKnowledgeBasePatch,
    SessionKnowledgeBasePut,
)
from app_layer_base.base.repos.base import BaseRepository


class SessionKnowledgeBaseRepository(
    BaseRepository[SessionKnowledgeBase, SessionKnowledgeBaseCreate, SessionKnowledgeBasePut, SessionKnowledgeBasePatch]
):
    model = SessionKnowledgeBase
