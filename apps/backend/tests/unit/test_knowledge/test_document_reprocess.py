import pytest
from app.features.knowledge.knowledge_base_documents.schemas import (
    KnowledgeBaseDocumentReprocessMode,
    KnowledgeBaseDocumentStatus,
)
from app.features.knowledge.knowledge_base_documents.usecases.reprocess import resolve_reprocess_mode
from fastapi import HTTPException


@pytest.mark.parametrize(
    ("status", "expected_mode"),
    [
        (KnowledgeBaseDocumentStatus.PENDING_REPARSE, KnowledgeBaseDocumentReprocessMode.REPARSE),
        (KnowledgeBaseDocumentStatus.PENDING_RECHUNK, KnowledgeBaseDocumentReprocessMode.RECHUNK),
        (KnowledgeBaseDocumentStatus.PENDING_REEMBED, KnowledgeBaseDocumentReprocessMode.REEMBED),
    ],
)
def test_resolve_reprocess_mode_auto_maps_supported_pending_statuses(
    status: KnowledgeBaseDocumentStatus,
    expected_mode: KnowledgeBaseDocumentReprocessMode,
) -> None:
    assert resolve_reprocess_mode(KnowledgeBaseDocumentReprocessMode.AUTO, status) == expected_mode


def test_resolve_reprocess_mode_explicit_mode_bypasses_status_mapping() -> None:
    assert (
        resolve_reprocess_mode(KnowledgeBaseDocumentReprocessMode.REEMBED, KnowledgeBaseDocumentStatus.COMPLETED)
        == KnowledgeBaseDocumentReprocessMode.REEMBED
    )


@pytest.mark.parametrize(
    "status",
    [
        KnowledgeBaseDocumentStatus.COMPLETED,
        KnowledgeBaseDocumentStatus.FAILED,
    ],
)
def test_resolve_reprocess_mode_auto_rejects_statuses_without_parsed_artifact_path(status: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        resolve_reprocess_mode(KnowledgeBaseDocumentReprocessMode.AUTO, status)

    assert exc_info.value.status_code == 409
