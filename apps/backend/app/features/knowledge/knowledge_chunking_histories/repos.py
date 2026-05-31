from app.features.knowledge.knowledge_chunking_histories.models import KnowledgeChunkingHistory
from app.features.knowledge.knowledge_chunking_histories.schemas import (
    KnowledgeChunkingHistoryCreate,
    KnowledgeChunkingHistoryPatch,
    KnowledgeChunkingHistoryPut,
)
from app_layer_base.base.repos.base import BaseRepository


class KnowledgeChunkingHistoryRepository(
    BaseRepository[
        KnowledgeChunkingHistory,
        KnowledgeChunkingHistoryCreate,
        KnowledgeChunkingHistoryPut,
        KnowledgeChunkingHistoryPatch,
    ]
):
    model = KnowledgeChunkingHistory
