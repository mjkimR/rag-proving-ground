import asyncio
from uuid import uuid4

import app.worker.scheduling as scheduling_module
import pytest
from app.features.knowledge.knowledge_base_documents.models import KnowledgeBaseDocument
from app.features.knowledge.knowledge_bases.models import KnowledgeBase
from app.worker.scheduling import dispatcher_loop, stop_dispatchers


@pytest.mark.asyncio
async def test_dispatcher_loop_schedules_round_robin(session, mocker):
    """Verify that the DB-polling dispatcher implements fair round-robin scheduling.

    It should fetch the oldest queued document from each active Knowledge Base,
    update their status to PARSING, and call the Taskiq task kicker on the
    appropriate priority queue.
    """
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

    mock_kicker = mocker.MagicMock()
    mock_kicker.with_labels.return_value = mock_kicker
    mock_kicker.kiq = mocker.AsyncMock()
    mocker.patch("app.worker.handlers.ingest.handle_parse.kicker", return_value=mock_kicker)

    mock_redis = mocker.MagicMock()
    mock_redis.get = mocker.AsyncMock(return_value=None)
    mock_redis.set = mocker.AsyncMock(return_value=True)
    mock_redis.llen = mocker.AsyncMock(return_value=0)
    mocker.patch("app.worker.scheduling.get_redis_client", mocker.AsyncMock(return_value=mock_redis))

    mock_rabbitmq_settings = mocker.MagicMock()
    mock_rabbitmq_settings.url = "amqp://guest:guest@localhost:5672/"
    mock_rabbitmq_settings.parse_queue_name = "kb_ingest_parse"
    mock_rabbitmq_settings.max_priority = 5
    mocker.patch("app.worker.scheduling.get_rabbitmq_settings", return_value=mock_rabbitmq_settings)

    mocker.patch("app.worker.scheduling.get_queue_message_count", mocker.AsyncMock(return_value=(None, None, 0)))

    stop_event = asyncio.Event()

    async def mock_sleep(seconds):
        stop_event.set()

    mocker.patch("asyncio.sleep", side_effect=mock_sleep)

    mock_broker = mocker.MagicMock()
    await dispatcher_loop(mock_broker, stop_event, "test-dispatcher-id")

    assert mock_kicker.kiq.call_count == 2

    with_labels_calls = mock_kicker.with_labels.call_args_list
    for call in with_labels_calls:
        assert call.kwargs.get("queue_name") == "kb_ingest_parse"

    priorities_passed = [call.kwargs.get("priority") for call in with_labels_calls]
    assert 4 in priorities_passed  # high priority
    assert 3 in priorities_passed  # medium priority
    assert 2 not in priorities_passed  # low priority not dispatched

    kiq_calls = mock_kicker.kiq.call_args_list
    dispatched_ids = [call[0][0].document_id for call in kiq_calls]
    assert doc1_1_id in dispatched_ids
    assert doc2_1_id in dispatched_ids
    assert doc1_2_id not in dispatched_ids

    await session.refresh(doc1_1)
    await session.refresh(doc1_2)
    await session.refresh(doc2_1)

    assert doc1_1.status == "PARSING"
    assert doc2_1.status == "PARSING"
    assert doc1_2.status == "QUEUED"


@pytest.mark.asyncio
async def test_stop_dispatchers_closes_redis(mocker):
    """Verify that stop_dispatchers() closes the Redis client on shutdown."""
    mock_close = mocker.patch(
        "app.worker.scheduling.close_redis_client",
        new_callable=mocker.AsyncMock,
    )

    stop_event = asyncio.Event()
    stop_event.set()
    mocker.patch.object(scheduling_module, "_stop_event", stop_event)
    mocker.patch.object(scheduling_module, "_dispatcher_task", None)

    await stop_dispatchers()

    mock_close.assert_called_once()
