import asyncio
from uuid import uuid4

import pytest
from app.features.knowledge.knowledge_base_documents.models import KnowledgeBaseDocument
from app.features.knowledge.knowledge_bases.models import KnowledgeBase
from app.worker.scheduling import dispatcher_loop


@pytest.mark.asyncio
async def test_dispatcher_loop_schedules_round_robin(session, mocker):
    """Verify that the DB-polling dispatcher implements fair round-robin scheduling.

    It should fetch the oldest queued document from each active Knowledge Base,
    update their status to PARSING, and call the Taskiq task kicker on the
    appropriate priority queue.
    """
    # 1. Seed two Knowledge Bases
    kb1_id = uuid4()
    kb2_id = uuid4()

    kb1 = KnowledgeBase(
        id=kb1_id,
        name="kb_1",
        status="READY",
        default_parsing_config={},
    )
    kb2 = KnowledgeBase(
        id=kb2_id,
        name="kb_2",
        status="READY",
        default_parsing_config={},
    )
    session.add_all([kb1, kb2])
    await session.commit()

    # 2. Seed 3 Documents in QUEUED status
    # KB1 has 2 documents, KB2 has 1 document
    doc1_1_id = uuid4()
    doc1_2_id = uuid4()
    doc2_1_id = uuid4()

    doc1_1 = KnowledgeBaseDocument(
        id=doc1_1_id,
        name="doc1_1.pdf",
        knowledge_base_id=kb1_id,
        status="QUEUED",
        priority="high",
        file_hash="hash1_1",
        document_info={"content_type": "application/pdf"},
    )
    doc1_2 = KnowledgeBaseDocument(
        id=doc1_2_id,
        name="doc1_2.pdf",
        knowledge_base_id=kb1_id,
        status="QUEUED",
        priority="low",
        file_hash="hash1_2",
        document_info={"content_type": "application/pdf"},
    )
    doc2_1 = KnowledgeBaseDocument(
        id=doc2_1_id,
        name="doc2_1.pdf",
        knowledge_base_id=kb2_id,
        status="QUEUED",
        priority="medium",
        file_hash="hash2_1",
        document_info={"content_type": "application/pdf"},
    )

    session.add_all([doc1_1, doc1_2, doc2_1])
    await session.commit()

    # 3. Mock the handle_parse task's kicker
    mock_kicker = mocker.MagicMock()
    mock_kicker.with_labels.return_value = mock_kicker
    mock_kicker.kiq = mocker.AsyncMock()
    mocker.patch("app.worker.handlers.ingest.handle_parse.kicker", return_value=mock_kicker)

    # Mock redis client and get_redis_client helper
    mock_redis = mocker.MagicMock()
    mock_redis.get = mocker.AsyncMock(return_value=None)
    mock_redis.set = mocker.AsyncMock(return_value=True)
    mock_redis.llen = mocker.AsyncMock(return_value=0)
    mocker.patch("app.worker.scheduling.get_redis_client", mocker.AsyncMock(return_value=mock_redis))

    # 4. Mock asyncio.sleep to stop the loop after one run
    stop_event = asyncio.Event()

    async def mock_sleep(seconds):
        stop_event.set()

    mocker.patch("asyncio.sleep", side_effect=mock_sleep)

    # 5. Run the dispatcher loop
    mock_broker = mocker.MagicMock()
    await dispatcher_loop(mock_broker, stop_event, "test-dispatcher-id")

    # 6. Verify assertions
    # KB1 should get doc1_1 (since it is the first/oldest document of KB1)
    # KB2 should get doc2_1 (since it is the only document of KB2)
    # doc1_2 should NOT be dispatched in this cycle (since it's ranked 2 for KB1, and the limit is N=1 per KB)
    assert mock_kicker.kiq.call_count == 2

    # Verify that kicker was called with the priority label
    with_labels_calls = mock_kicker.with_labels.call_args_list
    labels_passed = [c.kwargs.get("queue_name") for c in with_labels_calls]
    assert "kb_ingest:high" in labels_passed
    assert "kb_ingest:medium" in labels_passed
    assert "kb_ingest:low" not in labels_passed

    # Verify that kiq was called with correct message payloads
    kiq_calls = mock_kicker.kiq.call_args_list
    dispatched_ids = [call[0][0].document_id for call in kiq_calls]
    assert doc1_1_id in dispatched_ids
    assert doc2_1_id in dispatched_ids
    assert doc1_2_id not in dispatched_ids

    # Check status updates in DB:
    # doc1_1 and doc2_1 status should be PARSING
    # doc1_2 status should remain QUEUED
    await session.refresh(doc1_1)
    await session.refresh(doc1_2)
    await session.refresh(doc2_1)

    assert doc1_1.status == "PARSING"
    assert doc2_1.status == "PARSING"
    assert doc1_2.status == "QUEUED"
