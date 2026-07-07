from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from app.features.knowledge.knowledge_bases.models import KnowledgeBase
from app.features.knowledge.session_knowledge_bases.models import SessionKnowledgeBase
from app.features.storage.file_attachments.models import FileAttachment
from app.features.storage.file_attachments.processors import TempKbDocumentProcessor
from app.features.storage.session_file_attachments.models import SessionFileAttachment
from app.worker.handlers.attachment import process_file_attachment
from fastapi import status
from sqlalchemy import select


async def test_upload_file_attachment(app, monkeypatch) -> None:
    from httpx import ASGITransport, AsyncClient

    # 1. Mock MinIO storage client
    mock_storage = AsyncMock()
    monkeypatch.setattr(
        "app.features.storage.file_attachments.usecases.upload.get_storage_client",
        lambda: mock_storage,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # 2. Upload file
        file_content = b"hello test file content"
        files = {"file": ("document.pdf", file_content, "application/pdf")}
        resp = await client.post("/api/v1/file_attachments/upload", files=files)

        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["filename"] == "document.pdf"
        assert data["mime_type"] == "application/pdf"
        assert data["size_bytes"] == len(file_content)
        assert "sha256" in data
        assert data["storage_path"] == f"raw-attachments/{data['sha256']}"

        # Verify upload called on storage
        mock_storage.upload_file.assert_called_once_with(data["storage_path"], file_content)

        # 3. Upload same file again (deduplication check)
        mock_storage.upload_file.reset_mock()
        resp2 = await client.post("/api/v1/file_attachments/upload", files=files)
        assert resp2.status_code == status.HTTP_201_CREATED
        data2 = resp2.json()
        assert data2["id"] == data["id"]
        # Should reuse existing database record without uploading again
        mock_storage.upload_file.assert_not_called()


async def test_bind_file_to_session(client, session, monkeypatch) -> None:
    # 1. Create a FileAttachment record
    fa = FileAttachment(
        sha256="hash-123456",
        filename="test.txt",
        mime_type="text/plain",
        size_bytes=100,
        storage_path="raw-attachments/hash-123456",
    )
    session.add(fa)
    await session.commit()

    # 2. Mock Taskiq process task dispatch
    mock_task = MagicMock()
    mock_task.task_id = "task-uuid-456"
    mock_kiq = AsyncMock(return_value=mock_task)
    monkeypatch.setattr("app.common.task_dispatch.kick_task", mock_kiq)

    # 3. Request binding to session
    payload = {"thread_id": "thread-abc", "file_attachment_id": str(fa.id), "purpose": "temp_kb"}
    resp = await client.post("/api/v1/sessions/thread-abc/files", json=payload)

    if resp.status_code == 422:
        print("BIND API 422 Error:", resp.json())

    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert data["thread_id"] == "thread-abc"
    assert data["file_attachment_id"] == str(fa.id)
    assert data["purpose"] == "temp_kb"
    assert data["status"] == "PENDING"
    assert data["task_id"] == "task-uuid-456"

    # Verify taskiq task was dispatched
    from app.common.task_dispatch import PROCESS_FILE_ATTACHMENT_TASK

    mock_kiq.assert_called_once_with(PROCESS_FILE_ATTACHMENT_TASK, session_file_attachment_id=UUID(data["id"]))

    # 4. Request same binding again (idempotency check)
    mock_kiq.reset_mock()
    resp2 = await client.post("/api/v1/sessions/thread-abc/files", json=payload)
    assert resp2.status_code == status.HTTP_202_ACCEPTED
    data2 = resp2.json()
    assert data2["id"] == data["id"]
    assert data2["status"] == "PENDING"
    mock_kiq.assert_not_called()


async def test_process_file_attachment_task(session, monkeypatch) -> None:
    # 1. Prepare data
    fa = FileAttachment(
        sha256="hash-abc",
        filename="some.txt",
        mime_type="text/plain",
        size_bytes=50,
        storage_path="raw-attachments/hash-abc",
    )
    session.add(fa)
    await session.flush()

    sfa = SessionFileAttachment(
        thread_id="thread-xyz",
        file_attachment_id=fa.id,
        purpose="context",  # raw purpose (doesn't trigger processor logic)
        status="PENDING",
    )
    session.add(sfa)
    await session.commit()

    # 2. Mock storage client download
    mock_storage = AsyncMock()
    mock_storage.download_file.return_value = b"raw file bytes"
    monkeypatch.setattr(
        "app.worker.handlers.attachment.get_storage_client",
        lambda: mock_storage,
    )

    # 3. Run Taskiq handler task
    res = await process_file_attachment(sfa.id)
    assert "storage_path" in res
    assert res["storage_path"] == "raw-attachments/hash-abc"

    # 4. Verify DB status updated to COMPLETED
    await session.refresh(sfa)
    assert sfa.status == "COMPLETED"
    assert sfa.processed_metadata is not None
    assert "storage_path" in sfa.processed_metadata


async def test_temp_kb_document_processor(session, monkeypatch) -> None:
    # 1. Prepare file and session attachment
    fa = FileAttachment(
        sha256="hash-789",
        filename="notes.md",
        mime_type="text/markdown",
        size_bytes=40,
        storage_path="raw-attachments/hash-789",
    )
    session.add(fa)
    await session.flush()

    sfa = SessionFileAttachment(
        thread_id="thread-789",
        file_attachment_id=fa.id,
        purpose="temp_kb",
        status="PROCESSING",
    )
    session.add(sfa)
    await session.commit()

    # 2. Mock storage client
    mock_storage = AsyncMock()
    monkeypatch.setattr(
        "app.features.storage.file_attachments.processors.get_storage_client",
        lambda: mock_storage,
    )

    # 3. Mock RAG ingestion pipeline service
    mock_pipeline = AsyncMock()
    # Mock parse stage
    mock_parsed_doc = MagicMock()
    mock_parsed_doc.elements = []
    mock_parsed_doc.pages = []
    mock_pipeline.parse_or_load_cached.return_value = mock_parsed_doc

    # Mock chunk stage
    mock_chunks = [MagicMock()]
    mock_pipeline.rebuild_chunks.return_value = mock_chunks

    # Mock pipeline service builder
    monkeypatch.setattr(
        "app.features.storage.file_attachments.processors.build_pipeline_service",
        lambda: mock_pipeline,
    )

    # 4. Execute processor
    processor = TempKbDocumentProcessor()
    res = await processor.process(
        session_file_attachment_id=sfa.id,
        raw_file_bytes=b"my note contents",
        filename="notes.md",
        mime_type="text/markdown",
        sha256="hash-789",
    )

    assert "knowledge_base_id" in res
    assert "doc_id" in res
    assert res["chunk_count"] == 1

    # Verify temporary KB and SessionKnowledgeBase mapping were created
    kb_id = res["knowledge_base_id"]
    kb = await session.get(KnowledgeBase, UUID(kb_id))
    assert kb is not None
    assert kb.is_temp is True

    skb_stmt = select(SessionKnowledgeBase).where(SessionKnowledgeBase.thread_id == "thread-789")
    skb = (await session.execute(skb_stmt)).scalars().first()
    assert skb is not None
    assert skb.knowledge_base_id == kb.id

    # Verify pipeline service functions called
    mock_pipeline.parse_or_load_cached.assert_called_once()
    mock_pipeline.rebuild_chunks.assert_called_once()
    mock_pipeline.embed_chunks.assert_called_once()
