import asyncio
from uuid import uuid4

import app.worker.scheduling as scheduling_module
import pytest
from app.features.knowledge.knowledge_base_documents.schemas import ParseDocumentMessage
from app.worker.scheduling import (
    dispatcher_loop,
    enqueue_parse_document_message,
    stop_dispatchers,
)


@pytest.mark.asyncio
async def test_enqueue_parse_document_message(mocker):
    # Mock redis client and get_redis_client helper
    mock_redis = mocker.MagicMock()
    mock_redis.eval = mocker.AsyncMock(return_value=1)

    mocker.patch("app.worker.scheduling.get_redis_client", mocker.AsyncMock(return_value=mock_redis))

    kb_id = uuid4()
    msg = ParseDocumentMessage(
        document_id=uuid4(),
        knowledge_base_id=kb_id,
        file_hash="test-hash",
        filename="test.pdf",
        content_type="application/pdf",
        provider="docling",
    )

    await enqueue_parse_document_message(kb_id, msg, "docling")

    # Assertions
    mock_redis.eval.assert_called_once()
    eval_args = mock_redis.eval.call_args[0]

    # eval args should be: (script, numkeys, key1, key2, key3, arg1, arg2)
    assert len(eval_args) >= 7
    assert "SADD" in eval_args[0]  # Verify Lua script contains SADD
    assert eval_args[1] == 3
    assert eval_args[2] == "active_kbs:docling"
    assert eval_args[3] == "active_queues:docling"
    assert eval_args[4] == f"kb_queue:{kb_id}:docling"
    assert eval_args[5] == str(kb_id)
    assert eval_args[6] == msg.model_dump_json()


@pytest.mark.asyncio
async def test_dispatcher_loop_schedules_round_robin(mocker):
    """Verify the LMOVE-based Reliable Queue pattern and round-robin fair scheduling."""
    mock_redis = mocker.MagicMock()

    kb1_id = str(uuid4())
    kb2_id = str(uuid4())

    msg1 = ParseDocumentMessage(
        document_id=uuid4(),
        knowledge_base_id=uuid4(),
        file_hash="hash-1",
        filename="doc1.pdf",
        provider="docling",
    )
    msg2 = ParseDocumentMessage(
        document_id=uuid4(),
        knowledge_base_id=uuid4(),
        file_hash="hash-2",
        filename="doc2.pdf",
        provider="docling",
    )

    stop_event = asyncio.Event()

    # lpop: handles round-robin KB rotation (active_queues) and processing-queue cleanup
    lpop_counter = 0

    async def side_effect_lpop(key):
        nonlocal lpop_counter
        if key == "active_queues:docling":
            if lpop_counter == 0:
                lpop_counter += 1
                return kb1_id.encode("utf-8")
            elif lpop_counter == 1:
                lpop_counter += 1
                return kb2_id.encode("utf-8")
            else:
                stop_event.set()
                return None
        # processing queue cleanup after successful publish — return value unused
        return None

    mock_redis.lpop = mocker.AsyncMock(side_effect=side_effect_lpop)

    # lmove: atomically moves head of main queue → processing queue, returns the message.
    # No lindex needed: lmove both moves and returns the element atomically.
    async def side_effect_lmove(src, dst, src_where, dst_where):
        if src == f"kb_queue:{kb1_id}:docling" and dst == f"kb_queue:{kb1_id}:docling:processing":
            return msg1.model_dump_json().encode("utf-8")
        if src == f"kb_queue:{kb2_id}:docling" and dst == f"kb_queue:{kb2_id}:docling:processing":
            return msg2.model_dump_json().encode("utf-8")
        return None

    mock_redis.lmove = mocker.AsyncMock(side_effect=side_effect_lmove)

    # llen: remaining messages in the MAIN queue (not processing) after successful dispatch
    async def side_effect_llen(key):
        if key == f"kb_queue:{kb1_id}:docling":
            return 1  # KB1 still has pending messages → re-enqueue
        if key == f"kb_queue:{kb2_id}:docling":
            return 0  # KB2 exhausted → remove from active set
        return 0

    mock_redis.llen = mocker.AsyncMock(side_effect=side_effect_llen)

    mock_redis.rpush = mocker.AsyncMock()
    mock_redis.srem = mocker.AsyncMock()
    mock_redis.delete = mocker.AsyncMock()

    mocker.patch("app.worker.scheduling.get_redis_client", mocker.AsyncMock(return_value=mock_redis))

    mock_broker = mocker.MagicMock()
    mock_broker.publish = mocker.AsyncMock()

    await dispatcher_loop("docling", mock_broker, stop_event)

    # Both messages published to the correct provider-specific queue
    mock_broker.publish.assert_any_call(msg1, "document.parse.docling")
    mock_broker.publish.assert_any_call(msg2, "document.parse.docling")

    # After success, processing queue cleaned up via lpop(processing_key)
    mock_redis.lpop.assert_any_call(f"kb_queue:{kb1_id}:docling:processing")
    mock_redis.lpop.assert_any_call(f"kb_queue:{kb2_id}:docling:processing")

    # KB1 had remaining items in main queue → pushed back to round-robin list
    mock_redis.rpush.assert_any_call("active_queues:docling", kb1_id)

    # KB2 was exhausted → removed from active set (not pushed back)
    mock_redis.srem.assert_called_once_with("active_kbs:docling", kb2_id)

    # Distributed retry counter cleared via Redis DEL on each successful publish
    mock_redis.delete.assert_any_call(f"retry_counter:{kb1_id}:docling")
    mock_redis.delete.assert_any_call(f"retry_counter:{kb2_id}:docling")


@pytest.mark.asyncio
async def test_dispatcher_loop_dlq_isolation_on_max_retries(mocker):
    """KB is moved to DLQ and isolated after MAX_DISPATCH_RETRIES consecutive broker failures."""
    mock_redis = mocker.MagicMock()
    kb_id = str(uuid4())

    msg = ParseDocumentMessage(
        document_id=uuid4(),
        knowledge_base_id=uuid4(),
        file_hash="hash-bad",
        filename="bad.pdf",
        provider="docling",
    )
    msg_bytes = msg.model_dump_json().encode("utf-8")

    stop_event = asyncio.Event()

    # lpop: returns kb_id exactly MAX_DISPATCH_RETRIES times, then stops the loop
    lpop_counter = 0

    async def side_effect_lpop(key):
        nonlocal lpop_counter
        if key == "active_queues:docling":
            if lpop_counter < scheduling_module.MAX_DISPATCH_RETRIES:
                lpop_counter += 1
                return kb_id.encode("utf-8")
            else:
                stop_event.set()
                return None
        return None

    mock_redis.lpop = mocker.AsyncMock(side_effect=side_effect_lpop)

    # lmove: handles main→processing (fetch), processing→main (restore on retry),
    # and processing→dlq (final isolation)
    main_key = f"kb_queue:{kb_id}:docling"
    processing_key = f"kb_queue:{kb_id}:docling:processing"
    dlq_key = "dlq:docling"

    async def side_effect_lmove(src, dst, src_where, dst_where):
        if src == main_key and dst == processing_key:
            return msg_bytes  # fetch: move to processing
        if src == processing_key and dst == main_key:
            return msg_bytes  # restore: move back to main on retry
        if src == processing_key and dst == dlq_key:
            return msg_bytes  # isolate: move to DLQ
        return None

    mock_redis.lmove = mocker.AsyncMock(side_effect=side_effect_lmove)
    mock_redis.rpush = mocker.AsyncMock()
    mock_redis.srem = mocker.AsyncMock()
    mock_redis.delete = mocker.AsyncMock()
    # Returns 1, 2, 3 across the three consecutive broker failures
    mock_redis.incr = mocker.AsyncMock(side_effect=list(range(1, scheduling_module.MAX_DISPATCH_RETRIES + 1)))

    # No-op sleep so retry delays don't slow down the test
    mocker.patch("asyncio.sleep", mocker.AsyncMock())

    mocker.patch("app.worker.scheduling.get_redis_client", mocker.AsyncMock(return_value=mock_redis))

    mock_broker = mocker.MagicMock()
    mock_broker.publish = mocker.AsyncMock(side_effect=Exception("broker unavailable"))

    await dispatcher_loop("docling", mock_broker, stop_event)

    # --- DLQ assertions ---
    # processing→DLQ lmove must be called exactly once (on the final retry)
    dlq_moves = [c for c in mock_redis.lmove.call_args_list if c.args[1] == dlq_key]
    assert len(dlq_moves) == 1, "Message must be moved to DLQ exactly once after max retries"

    # KB must be removed from active set after DLQ isolation
    mock_redis.srem.assert_called_once_with("active_kbs:docling", kb_id)

    # KB must NOT be re-enqueued to active_queues after the final (DLQ) failure;
    # it should only be re-enqueued for the preceding retries (MAX - 1 times)
    active_queue_rpush_calls = [c for c in mock_redis.rpush.call_args_list if c.args[0] == "active_queues:docling"]
    assert len(active_queue_rpush_calls) == scheduling_module.MAX_DISPATCH_RETRIES - 1, (
        f"Expected {scheduling_module.MAX_DISPATCH_RETRIES - 1} re-enqueues before DLQ isolation, "
        f"got {len(active_queue_rpush_calls)}"
    )

    # Retry counter (Redis key) must be deleted after DLQ isolation
    retry_key = f"retry_counter:{kb_id}:docling"
    mock_redis.delete.assert_called_with(retry_key)

    # INCR must be called exactly once per failure attempt
    assert mock_redis.incr.call_count == scheduling_module.MAX_DISPATCH_RETRIES


@pytest.mark.asyncio
async def test_stop_dispatchers_closes_redis(mocker):
    """Verify that stop_dispatchers() triggers close_redis_client() on shutdown."""
    mock_close = mocker.patch(
        "app.worker.scheduling.close_redis_client",
        new_callable=mocker.AsyncMock,
    )

    # Simulate a clean shutdown state: stop event set, no running tasks
    stop_event = asyncio.Event()
    stop_event.set()
    mocker.patch.object(scheduling_module, "_stop_event", stop_event)
    mocker.patch.object(scheduling_module, "_dispatcher_tasks", [])

    await stop_dispatchers()

    mock_close.assert_called_once()
