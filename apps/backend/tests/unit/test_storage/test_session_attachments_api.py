from app.features.storage.file_attachments.models import FileAttachment
from app.features.storage.session_file_attachments.models import SessionFileAttachment
from fastapi import status


async def test_get_session_attachments_api(client, session) -> None:
    # 1. Create a FileAttachment record
    fa = FileAttachment(
        sha256="hash-session-test",
        filename="notes.md",
        mime_type="text/markdown",
        size_bytes=1024,
        storage_path="raw-attachments/hash-session-test",
    )
    session.add(fa)
    await session.flush()

    # 2. Create a SessionFileAttachment record bound to thread-test-123
    sfa = SessionFileAttachment(
        thread_id="thread-test-123",
        file_attachment_id=fa.id,
        purpose="temp_kb",
        status="COMPLETED",
        processed_metadata={
            "knowledge_base_id": "00000000-0000-0000-0000-000000000001",
            "doc_id": "00000000-0000-0000-0000-000000000002",
            "chunk_count": 5,
        },
    )
    session.add(sfa)
    await session.commit()

    # 3. Request session attachments from backend API
    resp = await client.get("/api/v1/sessions/thread-test-123/attachments")
    assert resp.status_code == status.HTTP_200_OK

    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["thread_id"] == "thread-test-123"
    assert data[0]["file_attachment_id"] == str(fa.id)
    assert data[0]["status"] == "COMPLETED"
    assert data[0]["purpose"] == "temp_kb"
    assert data[0]["processed_metadata"]["chunk_count"] == 5
