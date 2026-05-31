from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

# Import under test
from app.features.knowledge.knowledge_base_documents.usecases.ingest import IngestKnowledgeDocumentUseCase
from fastapi import HTTPException, UploadFile, status


@pytest.mark.asyncio
async def test_ingest_document_missing_filename() -> None:
    # Arrange
    file = MagicMock(spec=UploadFile)
    file.filename = ""

    use_case = IngestKnowledgeDocumentUseCase(
        kb_service=MagicMock(),
        doc_service=MagicMock(),
        parse_history_service=MagicMock(),
        chunk_history_service=MagicMock(),
        embed_history_service=MagicMock(),
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await use_case.execute(uuid4(), file)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Uploaded file must have a filename" in exc_info.value.detail


@pytest.mark.asyncio
async def test_ingest_document_invalid_extension() -> None:
    # Arrange
    file = MagicMock(spec=UploadFile)
    file.filename = "document.exe"

    use_case = IngestKnowledgeDocumentUseCase(
        kb_service=MagicMock(),
        doc_service=MagicMock(),
        parse_history_service=MagicMock(),
        chunk_history_service=MagicMock(),
        embed_history_service=MagicMock(),
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await use_case.execute(uuid4(), file)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Unsupported file type" in exc_info.value.detail


@pytest.mark.asyncio
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
        parse_history_service=MagicMock(),
        chunk_history_service=MagicMock(),
        embed_history_service=MagicMock(),
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await use_case.execute(uuid4(), file)

    assert exc_info.value.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    assert "Uploaded file size exceeds the 10MB limit" in exc_info.value.detail
