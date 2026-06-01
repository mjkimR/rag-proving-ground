from uuid import uuid4

import pytest
from app.features.knowledge.knowledge_base_documents.usecases import crud
from app.features.knowledge.knowledge_base_documents.usecases.crud import (
    KnowledgeDocumentCleanupTarget,
    cleanup_knowledge_document_assets,
)


class FailingStorageClient:
    async def list_files(self, prefix: str):
        raise RuntimeError(f"storage unavailable for {prefix}")
        yield ""


async def test_cleanup_knowledge_document_assets_collects_external_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    target = KnowledgeDocumentCleanupTarget(
        document_id=uuid4(),
        file_hash="file-hash",
        knowledge_base_name="kb",
        embed_config_hash="hash123",
    )

    async def fail_vector_cleanup(collection_name: str, document_id) -> None:
        raise RuntimeError(f"vector unavailable for {collection_name}/{document_id}")

    monkeypatch.setattr(crud, "delete_document_vectors", fail_vector_cleanup)
    monkeypatch.setattr(crud, "get_storage_client", lambda: FailingStorageClient())

    errors = await cleanup_knowledge_document_assets(target)

    assert len(errors) == 2
    assert "vector store cleanup failed" in errors[0]
    assert "storage cleanup failed" in errors[1]
