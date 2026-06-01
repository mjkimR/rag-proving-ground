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
        pipeline_service=MagicMock(),
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
        pipeline_service=MagicMock(),
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
        pipeline_service=MagicMock(),
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await use_case.execute(uuid4(), file)

    assert exc_info.value.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    assert "Uploaded file size exceeds the 10MB limit" in exc_info.value.detail
