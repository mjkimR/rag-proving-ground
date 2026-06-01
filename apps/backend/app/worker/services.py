"""Factory functions to build service instances for the worker process."""

from app.features.knowledge.knowledge_base_documents.facade.pipeline import KnowledgeDocumentPipelineService
from app.features.knowledge.knowledge_base_documents.repos import KnowledgeBaseDocumentRepository
from app.features.knowledge.knowledge_base_documents.services import KnowledgeBaseDocumentService
from app.features.knowledge.knowledge_bases.repos import KnowledgeBaseRepository
from app.features.knowledge.knowledge_bases.services import KnowledgeBaseService
from app.features.knowledge.knowledge_chunking_histories.repos import KnowledgeChunkingHistoryRepository
from app.features.knowledge.knowledge_chunking_histories.services import KnowledgeChunkingHistoryService
from app.features.knowledge.knowledge_embedding_histories.repos import KnowledgeEmbeddingHistoryRepository
from app.features.knowledge.knowledge_embedding_histories.services import KnowledgeEmbeddingHistoryService
from app.features.knowledge.knowledge_parsing_histories.repos import KnowledgeParsingHistoryRepository
from app.features.knowledge.knowledge_parsing_histories.services import KnowledgeParsingHistoryService


def build_pipeline_service() -> KnowledgeDocumentPipelineService:
    """Build KnowledgeDocumentPipelineService with manually wired dependencies."""
    kb_service = KnowledgeBaseService(repo=KnowledgeBaseRepository())
    doc_service = KnowledgeBaseDocumentService(repo=KnowledgeBaseDocumentRepository())
    parse_history_service = KnowledgeParsingHistoryService(repo=KnowledgeParsingHistoryRepository())
    chunk_history_service = KnowledgeChunkingHistoryService(repo=KnowledgeChunkingHistoryRepository())
    embed_history_service = KnowledgeEmbeddingHistoryService(repo=KnowledgeEmbeddingHistoryRepository())

    return KnowledgeDocumentPipelineService(
        kb_service=kb_service,
        doc_service=doc_service,
        parse_history_service=parse_history_service,
        chunk_history_service=chunk_history_service,
        embed_history_service=embed_history_service,
    )
