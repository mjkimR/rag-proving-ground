from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from app.features.knowledge.knowledge_base_documents.repos import KnowledgeBaseDocumentRepository
from app.features.knowledge.knowledge_base_documents.schemas import KnowledgeBaseDocumentStatus
from app.features.knowledge.knowledge_bases.repos import KnowledgeBaseRepository
from httpx import AsyncClient

from tests.utils import assert_status_code

pytestmark = pytest.mark.real_commit


async def test_knowledge_base_crud_and_document_listing(
    client: AsyncClient,
    make_db: Callable[..., Awaitable[Any]],
) -> None:
    kb = await make_db(
        KnowledgeBaseRepository,
        name="integration-kb",
        embedding_config={"model": "test-embedding", "distance": "cosine"},
        default_chunking_config={"chunk_size": 450, "chunk_overlap": 50},
        default_parsing_config={"provider": "docling"},
    )

    list_kb_response = await client.get("/api/v1/knowledge_bases")
    assert_status_code(list_kb_response, 200)
    assert any(item["id"] == str(kb.id) for item in list_kb_response.json()["items"])

    doc = await make_db(
        KnowledgeBaseDocumentRepository,
        name="guide.md",
        knowledge_base_id=kb.id,
        status=KnowledgeBaseDocumentStatus.COMPLETED,
        file_hash="abc123",
        document_info={
            "filename": "guide.md",
            "parsed_data_path": "knowledge/integration-kb/abc123/parsed_data.json",
        },
        parsing_config=None,
        chunking_config=None,
    )

    kb_docs_response = await client.get(f"/api/v1/knowledge_bases/{kb.id}/documents")
    assert_status_code(kb_docs_response, 200)
    kb_docs = kb_docs_response.json()["items"]
    assert [item["id"] for item in kb_docs] == [str(doc.id)]

    patch_kb_response = await client.patch(
        f"/api/v1/knowledge_bases/{kb.id}",
        json={"default_chunking_config": {"chunk_size": 256, "chunk_overlap": 25}},
    )
    assert_status_code(patch_kb_response, 200)

    get_doc_response = await client.get(f"/api/v1/knowledge_base_documents/{doc.id}")
    assert_status_code(get_doc_response, 200)
    assert get_doc_response.json()["status"] == KnowledgeBaseDocumentStatus.PENDING_RECHUNK
