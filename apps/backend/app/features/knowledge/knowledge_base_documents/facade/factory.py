"""Factory for the knowledge document pipeline service.

Lives with the facade so both the worker handlers and other features build the
pipeline from a single place without importing worker internals.
"""

from app.features.history.job_process_histories.repos import JobProcessHistoryRepository
from app.features.history.job_process_histories.services import JobProcessHistoryService
from app.features.knowledge.knowledge_base_documents.facade.pipeline import KnowledgeDocumentPipelineService
from app.features.knowledge.knowledge_base_documents.repos import KnowledgeBaseDocumentRepository
from app.features.knowledge.knowledge_base_documents.services import KnowledgeBaseDocumentService
from app.features.knowledge.knowledge_base_pages.repos import KnowledgeBasePageRepository
from app.features.knowledge.knowledge_base_pages.services import KnowledgeBasePageService
from app.features.knowledge.knowledge_bases.repos import KnowledgeBaseRepository
from app.features.knowledge.knowledge_bases.services import KnowledgeBaseService


def build_pipeline_service() -> KnowledgeDocumentPipelineService:
    """Build KnowledgeDocumentPipelineService with manually wired dependencies."""
    kb_service = KnowledgeBaseService(repo=KnowledgeBaseRepository())
    doc_service = KnowledgeBaseDocumentService(repo=KnowledgeBaseDocumentRepository())
    history_service = JobProcessHistoryService(repo=JobProcessHistoryRepository())
    page_service = KnowledgeBasePageService(repo=KnowledgeBasePageRepository())

    return KnowledgeDocumentPipelineService(
        kb_service=kb_service,
        doc_service=doc_service,
        history_service=history_service,
        page_service=page_service,
    )
