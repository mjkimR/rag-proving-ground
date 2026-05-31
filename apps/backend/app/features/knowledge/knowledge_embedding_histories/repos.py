from app.features.knowledge.knowledge_embedding_histories.models import KnowledgeEmbeddingHistory
from app.features.knowledge.knowledge_embedding_histories.schemas import (
    KnowledgeEmbeddingHistoryCreate,
    KnowledgeEmbeddingHistoryPatch,
    KnowledgeEmbeddingHistoryPut,
)
from app_layer_base.base.repos.base import BaseRepository


class KnowledgeEmbeddingHistoryRepository(
    BaseRepository[
        KnowledgeEmbeddingHistory,
        KnowledgeEmbeddingHistoryCreate,
        KnowledgeEmbeddingHistoryPut,
        KnowledgeEmbeddingHistoryPatch,
    ]
):
    model = KnowledgeEmbeddingHistory
