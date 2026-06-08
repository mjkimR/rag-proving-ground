from app.features.knowledge.knowledge_base_documents.schemas import (
    KnowledgeBaseDocumentReprocessMode,
    KnowledgeBaseDocumentStatus,
)
from app.features.knowledge.knowledge_base_documents.usecases.reprocess import resolve_reprocess_mode


def test_resolve_reprocess_mode_uses_pending_rechunk_status() -> None:
    mode = resolve_reprocess_mode(
        KnowledgeBaseDocumentReprocessMode.AUTO,
        KnowledgeBaseDocumentStatus.PENDING_RECHUNK,
    )

    assert mode == KnowledgeBaseDocumentReprocessMode.RECHUNK


def test_resolve_reprocess_mode_uses_pending_reembed_status() -> None:
    mode = resolve_reprocess_mode(
        KnowledgeBaseDocumentReprocessMode.AUTO,
        KnowledgeBaseDocumentStatus.PENDING_REEMBED,
    )

    assert mode == KnowledgeBaseDocumentReprocessMode.REEMBED


def test_resolve_reprocess_mode_uses_pending_reparse_status() -> None:
    mode = resolve_reprocess_mode(
        KnowledgeBaseDocumentReprocessMode.AUTO,
        KnowledgeBaseDocumentStatus.PENDING_REPARSE,
    )

    assert mode == KnowledgeBaseDocumentReprocessMode.REPARSE


def test_resolve_reprocess_mode_accepts_explicit_mode_for_completed_document() -> None:
    mode = resolve_reprocess_mode(
        KnowledgeBaseDocumentReprocessMode.RECHUNK,
        KnowledgeBaseDocumentStatus.COMPLETED,
    )

    assert mode == KnowledgeBaseDocumentReprocessMode.RECHUNK
