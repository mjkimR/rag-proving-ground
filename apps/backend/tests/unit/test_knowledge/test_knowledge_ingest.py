from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

# Import under test
from app.features.knowledge.knowledge_base_documents.usecases.ingest import (
    IngestKnowledgeDocumentUseCase,
    file_content_hash,
)
from fastapi import HTTPException, UploadFile, status


def test_file_content_hash_uses_sha256() -> None:
    assert file_content_hash(b"example") == "50d858e0985ecc7f60418aaf0cc5ab587f42c2570a884095a9e8ccacd0f6545c"


async def test_ingest_document_missing_filename() -> None:
    # Arrange
    file = MagicMock(spec=UploadFile)
    file.filename = ""

    use_case = IngestKnowledgeDocumentUseCase(
        kb_service=MagicMock(),
        doc_service=MagicMock(),
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await use_case.execute(uuid4(), file)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Uploaded file must have a filename" in exc_info.value.detail


async def test_ingest_document_invalid_extension() -> None:
    # Arrange
    file = MagicMock(spec=UploadFile)
    file.filename = "document.exe"

    use_case = IngestKnowledgeDocumentUseCase(
        kb_service=MagicMock(),
        doc_service=MagicMock(),
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await use_case.execute(uuid4(), file)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Unsupported file type" in exc_info.value.detail


async def test_ingest_document_oversized_file() -> None:
    # Arrange
    file = MagicMock(spec=UploadFile)
    file.filename = "document.pdf"

    # Simulate content larger than MAX_FILE_SIZE (10MB)
    oversized_content = b"x" * (10 * 1024 * 1024 + 10)
    file.read = AsyncMock(return_value=oversized_content)

    use_case = IngestKnowledgeDocumentUseCase(
        kb_service=MagicMock(),
        doc_service=MagicMock(),
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await use_case.execute(uuid4(), file)

    assert exc_info.value.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    assert "Uploaded file size exceeds the 10MB limit" in exc_info.value.detail


from app.features.knowledge.knowledge_base_documents.models import KnowledgeBaseDocument
from app.features.knowledge.knowledge_base_documents.repos import KnowledgeBaseDocumentRepository
from app.features.knowledge.knowledge_base_documents.schemas import KnowledgeBaseDocumentStatus


class _FakeTransaction:
    def __init__(self, session=None):
        if session is None:
            session = MagicMock()
            session.flush = AsyncMock()
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, traceback):
        return None


def create_mock_doc(doc_id, name, file_hash, status=KnowledgeBaseDocumentStatus.COMPLETED) -> MagicMock:
    doc = MagicMock(spec=KnowledgeBaseDocument)
    doc.id = doc_id
    doc.name = name
    doc.file_hash = file_hash
    doc.status = status
    doc.priority = "low"
    doc.document_info = {
        "parsing_config_hash": "stale_parse",
        "chunking_config_hash": "stale_chunk",
        "chunking_summary_hash": "stale_summary_hash",
        "chunk_count": 5,
        "original_file_path": "path/to/original",
        "parsed_data_path": "path/to/parsed",
        "chunked_data_path": "path/to/chunked",
    }
    doc.summary = "stale summary"
    doc.summary_model = "gpt-4o"
    doc.error_message = "some error"
    doc.parsing_config = None
    doc.chunking_config = None
    doc.knowledge_base_id = uuid4()
    return doc


def create_mock_repo() -> MagicMock:
    repo = MagicMock(spec=KnowledgeBaseDocumentRepository)
    repo.get_by_pk = AsyncMock()
    repo.get_all = AsyncMock()
    repo.get_by_pk_for_update = AsyncMock()
    repo.model = KnowledgeBaseDocument
    return repo


async def test_ingest_overwrite_different_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    kb_id = uuid4()
    doc_id = uuid4()
    filename = "document.pdf"
    content = b"new content"
    new_hash = file_content_hash(content)

    file = MagicMock(spec=UploadFile)
    file.filename = filename
    file.content_type = "application/pdf"
    file.read = AsyncMock(return_value=content)

    kb_service = MagicMock()
    doc_service = MagicMock()
    doc_service.repo = create_mock_repo()

    # Mock KB check
    kb_service.repo.get_by_pk = AsyncMock(return_value=MagicMock())

    # Mock finding existing doc with different hash
    existing_doc = create_mock_doc(
        doc_id=doc_id, name=filename, file_hash="old_hash", status=KnowledgeBaseDocumentStatus.COMPLETED
    )
    doc_service.repo.get_all.return_value = [existing_doc]

    # Mock second retrieve in transaction (step 4)
    doc_service.repo.get_by_pk.return_value = existing_doc

    # Mock transaction and storage
    monkeypatch.setattr(
        "app.features.knowledge.knowledge_base_documents.usecases.ingest.AsyncTransaction",
        _FakeTransaction,
    )
    mock_storage = AsyncMock()
    monkeypatch.setattr(
        "app.features.knowledge.knowledge_base_documents.usecases.ingest.get_storage_client",
        lambda: mock_storage,
    )
    monkeypatch.setattr(
        "app.features.knowledge.knowledge_base_documents.usecases.ingest.refresh_knowledge_base_status",
        AsyncMock(),
    )

    use_case = IngestKnowledgeDocumentUseCase(kb_service=kb_service, doc_service=doc_service)

    # Act
    response = await use_case.execute(kb_id, file, background_tasks=MagicMock())

    # Assert
    assert response["id"] == str(doc_id)
    assert existing_doc.file_hash == new_hash
    assert existing_doc.status == KnowledgeBaseDocumentStatus.QUEUED
    assert existing_doc.summary is None
    assert existing_doc.summary_model is None
    assert existing_doc.error_message is None
    assert "parsing_config_hash" not in existing_doc.document_info
    assert "chunking_config_hash" not in existing_doc.document_info
    assert "chunk_count" not in existing_doc.document_info
    assert existing_doc.document_info["filename"] == filename


async def test_ingest_same_hash_already_completed(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    kb_id = uuid4()
    doc_id = uuid4()
    filename = "document.pdf"
    content = b"same content"
    hash_val = file_content_hash(content)

    file = MagicMock(spec=UploadFile)
    file.filename = filename
    file.content_type = "application/pdf"
    file.read = AsyncMock(return_value=content)

    kb_service = MagicMock()
    doc_service = MagicMock()
    doc_service.repo = create_mock_repo()

    kb_service.repo.get_by_pk = AsyncMock(return_value=MagicMock())

    # Existing doc has identical hash and is already COMPLETED
    existing_doc = create_mock_doc(
        doc_id=doc_id, name=filename, file_hash=hash_val, status=KnowledgeBaseDocumentStatus.COMPLETED
    )
    doc_service.repo.get_all.return_value = [existing_doc]
    doc_service.repo.get_by_pk.return_value = existing_doc

    monkeypatch.setattr(
        "app.features.knowledge.knowledge_base_documents.usecases.ingest.AsyncTransaction",
        _FakeTransaction,
    )
    mock_storage = AsyncMock()
    monkeypatch.setattr(
        "app.features.knowledge.knowledge_base_documents.usecases.ingest.get_storage_client",
        lambda: mock_storage,
    )
    monkeypatch.setattr(
        "app.features.knowledge.knowledge_base_documents.usecases.ingest.refresh_knowledge_base_status",
        AsyncMock(),
    )

    use_case = IngestKnowledgeDocumentUseCase(kb_service=kb_service, doc_service=doc_service)

    # Act
    response = await use_case.execute(kb_id, file)

    # Assert
    assert response["id"] == str(doc_id)
    assert existing_doc.status == KnowledgeBaseDocumentStatus.COMPLETED  # Should NOT change to QUEUED
    assert existing_doc.summary == "stale summary"  # Should NOT clear summary


async def test_ingest_same_hash_failed_requeues(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    kb_id = uuid4()
    doc_id = uuid4()
    filename = "document.pdf"
    content = b"failed content"
    hash_val = file_content_hash(content)

    file = MagicMock(spec=UploadFile)
    file.filename = filename
    file.content_type = "application/pdf"
    file.read = AsyncMock(return_value=content)

    kb_service = MagicMock()
    doc_service = MagicMock()
    doc_service.repo = create_mock_repo()

    kb_service.repo.get_by_pk = AsyncMock(return_value=MagicMock())

    # Existing doc has identical hash but status is FAILED
    existing_doc = create_mock_doc(
        doc_id=doc_id, name=filename, file_hash=hash_val, status=KnowledgeBaseDocumentStatus.FAILED
    )
    doc_service.repo.get_all.return_value = [existing_doc]
    doc_service.repo.get_by_pk.return_value = existing_doc

    monkeypatch.setattr(
        "app.features.knowledge.knowledge_base_documents.usecases.ingest.AsyncTransaction",
        _FakeTransaction,
    )
    mock_storage = AsyncMock()
    monkeypatch.setattr(
        "app.features.knowledge.knowledge_base_documents.usecases.ingest.get_storage_client",
        lambda: mock_storage,
    )
    monkeypatch.setattr(
        "app.features.knowledge.knowledge_base_documents.usecases.ingest.refresh_knowledge_base_status",
        AsyncMock(),
    )

    use_case = IngestKnowledgeDocumentUseCase(kb_service=kb_service, doc_service=doc_service)

    # Act
    response = await use_case.execute(kb_id, file)

    # Assert
    assert response["id"] == str(doc_id)
    assert existing_doc.status == KnowledgeBaseDocumentStatus.QUEUED  # Should change to QUEUED to retry
    assert existing_doc.error_message is None


async def test_ingest_overwrite_triggers_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    kb_id = uuid4()
    doc_id = uuid4()
    filename = "document.pdf"
    content = b"new content"

    file = MagicMock(spec=UploadFile)
    file.filename = filename
    file.content_type = "application/pdf"
    file.read = AsyncMock(return_value=content)

    kb_service = MagicMock()
    doc_service = MagicMock()
    doc_service.repo = create_mock_repo()

    kb_service.repo.get_by_pk = AsyncMock(return_value=MagicMock())

    existing_doc = create_mock_doc(
        doc_id=doc_id, name=filename, file_hash="old_hash", status=KnowledgeBaseDocumentStatus.COMPLETED
    )
    doc_service.repo.get_all.return_value = [existing_doc]
    doc_service.repo.get_by_pk.return_value = existing_doc

    monkeypatch.setattr(
        "app.features.knowledge.knowledge_base_documents.usecases.ingest.AsyncTransaction",
        _FakeTransaction,
    )
    mock_storage = AsyncMock()
    monkeypatch.setattr(
        "app.features.knowledge.knowledge_base_documents.usecases.ingest.get_storage_client",
        lambda: mock_storage,
    )
    monkeypatch.setattr(
        "app.features.knowledge.knowledge_base_documents.usecases.ingest.refresh_knowledge_base_status",
        AsyncMock(),
    )

    cleanup_mock = AsyncMock()
    monkeypatch.setattr(
        "app.features.knowledge.knowledge_base_documents.usecases.ingest.cleanup_knowledge_document_assets",
        cleanup_mock,
    )

    background_tasks = MagicMock()
    use_case = IngestKnowledgeDocumentUseCase(kb_service=kb_service, doc_service=doc_service)

    # Act
    await use_case.execute(kb_id, file, background_tasks=background_tasks)

    # Assert
    background_tasks.add_task.assert_called_once()
    _, called_target = background_tasks.add_task.call_args[0]
    assert called_target.file_hash == "old_hash"
    assert called_target.document_id == doc_id
