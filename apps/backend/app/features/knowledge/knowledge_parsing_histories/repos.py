from app.features.knowledge.knowledge_parsing_histories.models import KnowledgeParsingHistory
from app.features.knowledge.knowledge_parsing_histories.schemas import (
    KnowledgeParsingHistoryCreate,
    KnowledgeParsingHistoryPatch,
    KnowledgeParsingHistoryPut,
)
from app_layer_base.base.repos.base import BaseRepository


class KnowledgeParsingHistoryRepository(
    BaseRepository[
        KnowledgeParsingHistory, KnowledgeParsingHistoryCreate, KnowledgeParsingHistoryPut, KnowledgeParsingHistoryPatch
    ]
):
    model = KnowledgeParsingHistory
