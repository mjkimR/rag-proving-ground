import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.features.knowledge.knowledge_base_documents.facade.pipeline import (
    KnowledgeDocumentPipelineService,
    PipelineStageContext,
    knowledge_chunked_data_key,
    knowledge_original_file_key,
    knowledge_parsed_data_key,
)
from rag_core.chunkers import ChunkedDocument, ChunkingConfig
from rag_core.parsers import ParsedDocument


def test_knowledge_storage_keys_resolved_under_file_hash() -> None:
    assert knowledge_original_file_key("kb", "abc123", "doc.pdf") == "knowledge/kb/abc123/doc.pdf"
    assert knowledge_parsed_data_key("kb", "abc123") == "knowledge/kb/abc123/parsed_data.json"
    assert knowledge_chunked_data_key("kb", "abc123") == "knowledge/kb/abc123/chunked_data.json"


from app.features.knowledge.knowledge_base_documents.models import KnowledgeBaseDocument


class _FakeTransaction:
    def __init__(self, session_mock=None):
        self.session_mock = session_mock or AsyncMock()

    async def __aenter__(self):
        return self.session_mock

    async def __aexit__(self, exc_type, exc, traceback):
        return None


async def test_rebuild_chunks_cache_hit(monkeypatch) -> None:
    # Configure session execute
    session_mock = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = ["CHUNKING"]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    session_mock.execute.return_value = mock_result

    # Mock AsyncTransaction
    monkeypatch.setattr(
        "app.features.knowledge.knowledge_base_documents.facade.pipeline.AsyncTransaction",
        lambda: _FakeTransaction(session_mock),
    )

    # Mock get_storage_client
    mock_storage = AsyncMock()
    mock_storage.file_exists.return_value = True
    chunks_data = [
        {
            "chunk_id": "chunk_1",
            "doc_id": "doc_1",
            "page_content": "hello world",
            "order": 1,
            "source_element_ids": [],
            "page_ids": [],
            "metadata": {},
        }
    ]
    mock_storage.download_file.return_value = json.dumps(chunks_data).encode("utf-8")
    monkeypatch.setattr(
        "app.features.knowledge.knowledge_base_documents.facade.pipeline.get_storage_client",
        lambda: mock_storage,
    )

    # Mock services
    kb_service = MagicMock()
    doc_service = MagicMock()
    history_service = MagicMock()
    page_service = MagicMock()

    doc_service.repo.model = KnowledgeBaseDocument

    doc_id = uuid4()
    mock_kb = MagicMock()
    mock_kb.name = "my_kb"
    mock_doc = MagicMock()
    mock_doc.file_hash = "hash123"
    mock_doc.knowledge_base_id = uuid4()

    # Existing chunk config hash matches
    config = ChunkingConfig(chunk_size=450, chunk_overlap=50)
    from rag_core.chunkers import knowledge_chunking_config_hash

    config_hash = knowledge_chunking_config_hash(config)
    mock_doc.document_info = {"chunking_config_hash": config_hash, "chunked_data_path": "some_path"}

    kb_service.repo.get_by_pk = AsyncMock(return_value=mock_kb)
    doc_service.repo.get_by_pk = AsyncMock(return_value=mock_doc)
    doc_service.repo.update_by_pk = AsyncMock()
    history_service.record = AsyncMock()

    service = KnowledgeDocumentPipelineService(
        kb_service=kb_service,
        doc_service=doc_service,
        history_service=history_service,
        page_service=page_service,
    )
    service.doc_service.repo.get_by_pk_for_update = AsyncMock(return_value=mock_doc)

    parsed_doc = ParsedDocument(doc_id="doc_1", parser="test-parser", pages=[], elements=[], metadata={})

    # Call rebuild_chunks
    chunks = await service.rebuild_chunks(
        document_id=doc_id,
        filename="test.pdf",
        parsed_doc=parsed_doc,
        chunking_config=config,
        stage_context=PipelineStageContext(name_prefix="Chunk", record_history=True),
    )

    # Verify cache hit path
    assert len(chunks) == 1
    assert chunks[0].page_content == "hello world"
    assert mock_storage.file_exists.call_count == 2
    mock_storage.download_file.assert_called_once()
    mock_storage.upload_file.assert_not_called()

    # Verify history recorded with cache hit name
    history_service.record.assert_called_once()
    history_args = history_service.record.call_args[0][1]
    assert "cache hit" in history_args.name
    assert history_args.metrics["cache_hit"] is True


async def test_rebuild_chunks_cache_miss(monkeypatch, mocker) -> None:
    # Configure session execute
    session_mock = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = ["CHUNKING"]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    session_mock.execute.return_value = mock_result

    # Mock AsyncTransaction
    monkeypatch.setattr(
        "app.features.knowledge.knowledge_base_documents.facade.pipeline.AsyncTransaction",
        lambda: _FakeTransaction(session_mock),
    )

    # Mock get_storage_client
    mock_storage = AsyncMock()
    mock_storage.file_exists.return_value = False
    mock_storage.upload_file = AsyncMock()
    monkeypatch.setattr(
        "app.features.knowledge.knowledge_base_documents.facade.pipeline.get_storage_client",
        lambda: mock_storage,
    )

    # Mock chunk_document
    fake_chunk = ChunkedDocument(
        chunk_id="chunk_2",
        doc_id="doc_1",
        page_content="chunked content",
        order=1,
        source_element_ids=[],
        page_ids=[],
        metadata={},
    )
    mocker.patch(
        "app.features.knowledge.knowledge_base_documents.facade.pipeline.chunk_document",
        return_value=[fake_chunk],
    )

    # Mock services
    kb_service = MagicMock()
    doc_service = MagicMock()
    history_service = MagicMock()
    page_service = MagicMock()

    doc_service.repo.model = KnowledgeBaseDocument

    doc_id = uuid4()
    mock_kb = MagicMock()
    mock_kb.name = "my_kb"
    mock_doc = MagicMock()
    mock_doc.file_hash = "hash123"
    mock_doc.document_info = {}  # Empty/no hash

    kb_id = uuid4()
    kb_service.repo.get_by_pk = AsyncMock(return_value=mock_kb)
    mock_doc.knowledge_base_id = kb_id
    doc_service.repo.get_by_pk = AsyncMock(return_value=mock_doc)
    doc_service.repo.update_by_pk = AsyncMock()
    history_service.record = AsyncMock()

    service = KnowledgeDocumentPipelineService(
        kb_service=kb_service,
        doc_service=doc_service,
        history_service=history_service,
        page_service=page_service,
    )
    service.doc_service.repo.get_by_pk_for_update = AsyncMock(return_value=mock_doc)

    parsed_doc = ParsedDocument(doc_id="doc_1", parser="test-parser", pages=[], elements=[], metadata={})

    config = ChunkingConfig(chunk_size=450, chunk_overlap=50)

    # Call rebuild_chunks
    chunks = await service.rebuild_chunks(
        document_id=doc_id,
        filename="test.pdf",
        parsed_doc=parsed_doc,
        chunking_config=config,
        stage_context=PipelineStageContext(name_prefix="Chunk", record_history=True),
    )

    # Verify cache miss path
    assert len(chunks) == 1
    assert chunks[0].page_content == "chunked content"
    mock_storage.file_exists.assert_not_called()
    mock_storage.upload_file.assert_called_once()

    # Verify history recorded with success name
    history_service.record.assert_called_once()
    history_args = history_service.record.call_args[0][1]
    assert "success" in history_args.name
    assert history_args.metrics["cache_hit"] is False

    # Check updated document_info
    assert mock_doc.document_info["chunk_count"] == 1
    assert "chunking_config_hash" in mock_doc.document_info
    assert mock_doc.document_info["chunked_data_path"] == f"knowledge/{kb_id}/hash123/chunked_data.json"
