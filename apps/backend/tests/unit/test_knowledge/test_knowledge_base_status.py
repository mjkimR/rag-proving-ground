from collections.abc import Sequence

import pytest
from app.features.knowledge.knowledge_base_documents.schemas import KnowledgeBaseDocumentStatus
from app.features.knowledge.knowledge_bases.schemas import KnowledgeBaseStatus
from app.features.knowledge.knowledge_bases.status import resolve_knowledge_base_status


@pytest.mark.parametrize(
    ("document_statuses", "expected_status"),
    [
        ([], KnowledgeBaseStatus.READY),
        ([KnowledgeBaseDocumentStatus.QUEUED], KnowledgeBaseStatus.RUNNING),
        ([KnowledgeBaseDocumentStatus.PARSING], KnowledgeBaseStatus.RUNNING),
        ([KnowledgeBaseDocumentStatus.CHUNKING], KnowledgeBaseStatus.RUNNING),
        ([KnowledgeBaseDocumentStatus.EMBEDDING], KnowledgeBaseStatus.RUNNING),
        ([KnowledgeBaseDocumentStatus.PENDING_REPARSE], KnowledgeBaseStatus.RUNNING),
        ([KnowledgeBaseDocumentStatus.PENDING_RECHUNK], KnowledgeBaseStatus.RUNNING),
        ([KnowledgeBaseDocumentStatus.PENDING_REEMBED], KnowledgeBaseStatus.RUNNING),
        ([KnowledgeBaseDocumentStatus.DELETING], KnowledgeBaseStatus.RUNNING),
        ([KnowledgeBaseDocumentStatus.FAILED], KnowledgeBaseStatus.FAILED),
        ([KnowledgeBaseDocumentStatus.COMPLETED], KnowledgeBaseStatus.COMPLETED),
        ([KnowledgeBaseDocumentStatus.COMPLETED, KnowledgeBaseDocumentStatus.READY], KnowledgeBaseStatus.READY),
        ([KnowledgeBaseDocumentStatus.COMPLETED, KnowledgeBaseDocumentStatus.FAILED], KnowledgeBaseStatus.FAILED),
        ([KnowledgeBaseDocumentStatus.FAILED, KnowledgeBaseDocumentStatus.QUEUED], KnowledgeBaseStatus.RUNNING),
    ],
)
def test_resolve_knowledge_base_status(
    document_statuses: Sequence[str],
    expected_status: KnowledgeBaseStatus,
) -> None:
    assert resolve_knowledge_base_status(document_statuses) == expected_status


def test_resolve_knowledge_base_status_preserves_deleting_status() -> None:
    status = resolve_knowledge_base_status(
        [KnowledgeBaseDocumentStatus.COMPLETED],
        current_status=KnowledgeBaseStatus.DELETING,
    )

    assert status == KnowledgeBaseStatus.DELETING
