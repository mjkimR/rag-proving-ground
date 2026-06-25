import json
from unittest.mock import AsyncMock

from app.features.knowledge.knowledge_base_documents.models import KnowledgeBaseDocument
from app.features.knowledge.knowledge_bases.models import KnowledgeBase
from fastapi import status


async def test_get_document_chunks_api(client, session, monkeypatch) -> None:
    # 1. Create a KnowledgeBase and a Document
    kb = KnowledgeBase(
        name="test-kb-for-chunks",
        status="READY",
    )
    session.add(kb)
    await session.flush()

    doc = KnowledgeBaseDocument(
        name="sample.txt",
        knowledge_base_id=kb.id,
        status="COMPLETED",
        file_hash="hash-sample-file",
        document_info={
            "filename": "sample.txt",
            "chunked_data_path": f"knowledge/{kb.id}/hash-sample-file/chunked_data.json",
        },
    )
    session.add(doc)
    await session.commit()

    # 2. Mock storage client
    mock_storage = AsyncMock()
    mock_storage.file_exists.return_value = True

    # Return mocked chunk JSON list
    mock_chunks = [
        {"content": "This is chunk 1 text content.", "page_content": "This is chunk 1 text content."},
        {"content": "This is chunk 2 text content.", "page_content": "This is chunk 2 text content."},
    ]
    mock_storage.download_file.return_value = json.dumps(mock_chunks).encode("utf-8")

    monkeypatch.setattr(
        "app.features.knowledge.knowledge_base_documents.usecases.assets.get_storage_client",
        lambda: mock_storage,
    )

    # 3. Call endpoint
    resp = await client.get(f"/api/v1/knowledge_base_documents/{doc.id}/chunks")
    assert resp.status_code == status.HTTP_200_OK

    data = resp.json()
    assert data["doc_id"] == str(doc.id)
    assert data["total_chunks"] == 2
    assert data["chunks"] == [
        "This is chunk 1 text content.",
        "This is chunk 2 text content.",
    ]

    assert doc.document_info is not None
    chunked_data_path = doc.document_info.get("chunked_data_path")
    assert chunked_data_path is not None
    mock_storage.file_exists.assert_called_once_with(chunked_data_path)
    mock_storage.download_file.assert_called_once_with(chunked_data_path)
