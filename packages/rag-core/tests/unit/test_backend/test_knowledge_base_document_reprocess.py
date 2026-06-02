import pytest
from app.features.knowledge.knowledge_base_documents.schemas import (
    KnowledgeBaseDocumentReprocessMode,
    KnowledgeBaseDocumentStatus,
)
from app.features.knowledge.knowledge_base_documents.usecases.reprocess import resolve_reprocess_mode
from fastapi import HTTPException, status


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


def test_resolve_reprocess_mode_rejects_pending_reparse() -> None:
    with pytest.raises(HTTPException) as exc_info:
        resolve_reprocess_mode(
            KnowledgeBaseDocumentReprocessMode.AUTO,
            KnowledgeBaseDocumentStatus.PENDING_REPARSE,
        )

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert "requires reparse" in exc_info.value.detail


def test_resolve_reprocess_mode_accepts_explicit_mode_for_completed_document() -> None:
    mode = resolve_reprocess_mode(
        KnowledgeBaseDocumentReprocessMode.RECHUNK,
        KnowledgeBaseDocumentStatus.COMPLETED,
    )

    assert mode == KnowledgeBaseDocumentReprocessMode.RECHUNK
