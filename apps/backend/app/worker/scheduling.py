"""DB-polling staging queue and fair round-robin scheduling dispatchers."""

import asyncio
from typing import Any, cast
from uuid import uuid4

import redis.asyncio as aioredis
from app.features.knowledge.knowledge_base_documents.schemas import ParseDocumentMessage
from loguru import logger
from rag_core.config import get_redis_settings

_redis_client: aioredis.Redis | None = None
_dispatcher_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None
_dispatcher_id: str | None = None

DISPATCH_TRIGGER_LIMIT = 2
SLEEP_INTERVALS = [0.2, 0.5, 1.0, 2.0, 3.0]


async def get_redis_client() -> aioredis.Redis:
    """Return the global Redis client instance, initializing it if necessary."""
    global _redis_client
    if _redis_client is None:
        settings = get_redis_settings()
        _redis_client = aioredis.from_url(
            settings.url,
            encoding="utf-8",
            decode_responses=False,
            max_connections=10,
        )
    return _redis_client


async def close_redis_client() -> None:
    """Close the global Redis client."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


async def dispatcher_loop(
    broker: Any,
    stop_event: asyncio.Event,
    dispatcher_id: str,
) -> None:
    """Background dispatcher loop that polls the database for QUEUED or PENDING_REPARSE documents

    and dispatches them to Taskiq in a fair round-robin manner.
    """
    logger.info(f"Starting DB-polling scheduling dispatcher loop (ID: {dispatcher_id})...")
    from app.features.knowledge.knowledge_base_documents.models import KnowledgeBaseDocument
    from app.features.knowledge.knowledge_base_documents.schemas import get_queue_name
    from app.features.knowledge.knowledge_bases.models import KnowledgeBase
    from app.worker.handlers.ingest import handle_parse
    from app_layer_base.core.database.transaction import AsyncTransaction
    from rag_core.parsers import resolve_knowledge_parsing_config
    from sqlalchemy import func, select, update

    sleep_index = 0
    while not stop_event.is_set():
        try:
            # 1. Leader election / Lock renewal using Redis
            redis_client = await get_redis_client()
            lock_key = "lock:dispatcher"

            # Check who holds the lock currently
            current_holder_bytes = await redis_client.get(lock_key)
            current_holder = (
                current_holder_bytes.decode("utf-8")
                if isinstance(current_holder_bytes, bytes)
                else current_holder_bytes
            )

            if current_holder is None:
                # Try to acquire the lock
                acquired = await redis_client.set(lock_key, dispatcher_id, ex=5, nx=True)
                if not acquired:
                    await asyncio.sleep(2.0)
                    continue
            elif current_holder != dispatcher_id:
                # Someone else is the active leader, skip this cycle
                await asyncio.sleep(2.0)
                continue
            else:
                # We are the active leader, renew our lock TTL
                await redis_client.expire(lock_key, 5)

            # 2. Check the total number of waiting tasks in Redis priority queues
            total_waiting = 0
            for queue in ["critical", "high", "medium", "low", "lowest"]:
                physical_queue = get_queue_name(queue)
                total_waiting += await cast(Any, redis_client.llen(physical_queue))

            if total_waiting > DISPATCH_TRIGGER_LIMIT:
                # Taskiq queues have enough buffer tasks, wait and check again using progressive backoff
                sleep_time = SLEEP_INTERVALS[sleep_index]
                sleep_index = min(sleep_index + 1, len(SLEEP_INTERVALS) - 1)
                await asyncio.sleep(sleep_time)
                continue

            docs_to_dispatch = []
            async with AsyncTransaction() as session:
                # 3. Window function query to select candidate documents per KB using a CTE
                candidates_cte = (
                    select(
                        KnowledgeBaseDocument.id,
                        func.row_number()
                        .over(
                            partition_by=KnowledgeBaseDocument.knowledge_base_id,
                            order_by=KnowledgeBaseDocument.created_at.asc(),
                        )
                        .label("rn"),
                    )
                    .where(KnowledgeBaseDocument.status.in_(["QUEUED", "PENDING_REPARSE"]))
                    .cte("candidates")
                )

                # Lock the target candidate documents atomically using FOR UPDATE SKIP LOCKED
                # (1st Step: select candidate IDs under row lock)
                lock_stmt = (
                    select(KnowledgeBaseDocument.id)
                    .where(KnowledgeBaseDocument.id.in_(select(candidates_cte.c.id).where(candidates_cte.c.rn == 1)))
                    .where(KnowledgeBaseDocument.status.in_(["QUEUED", "PENDING_REPARSE"]))
                    .with_for_update(skip_locked=True)
                )
                result = await session.execute(lock_stmt)
                locked_ids = [r[0] for r in result.all()]

                docs = []
                if locked_ids:
                    # Update status of locked documents to PARSING (2nd Step: atomic update)
                    update_stmt = (
                        update(KnowledgeBaseDocument)
                        .where(KnowledgeBaseDocument.id.in_(locked_ids))
                        .values(status="PARSING")
                        .returning(
                            KnowledgeBaseDocument.id,
                            KnowledgeBaseDocument.knowledge_base_id,
                            KnowledgeBaseDocument.priority,
                            KnowledgeBaseDocument.name,
                            KnowledgeBaseDocument.file_hash,
                            KnowledgeBaseDocument.document_info,
                        )
                    )
                    update_result = await session.execute(update_stmt)
                    docs = update_result.all()

                if docs:
                    # Bulk fetch KnowledgeBase configurations to resolve default_parsing_config
                    # while avoiding N+1 queries.
                    kb_ids = list({d.knowledge_base_id for d in docs})
                    kb_stmt = select(KnowledgeBase.id, KnowledgeBase.default_parsing_config).where(
                        KnowledgeBase.id.in_(kb_ids)
                    )
                    kb_result = await session.execute(kb_stmt)
                    kb_configs = {r.id: r.default_parsing_config for r in kb_result.all()}

                    logger.info(f"Dispatcher enqueuing fair batch of {len(docs)} document(s)")

                    for doc in docs:
                        default_parsing_config = kb_configs.get(doc.knowledge_base_id)
                        resolved_config = resolve_knowledge_parsing_config(default_parsing_config)
                        provider = resolved_config.get_provider_for_filename(doc.name)

                        docs_to_dispatch.append(
                            {
                                "document_id": doc.id,
                                "knowledge_base_id": doc.knowledge_base_id,
                                "file_hash": doc.file_hash,
                                "filename": doc.name,
                                "content_type": doc.document_info.get("content_type") if doc.document_info else None,
                                "provider": provider,
                                "priority": doc.priority,
                            }
                        )

            # Dispatch outside transaction with publish failure rollback to preserve status consistency
            dispatched_ids = []
            try:
                for d in docs_to_dispatch:
                    msg = ParseDocumentMessage(
                        document_id=d["document_id"],
                        knowledge_base_id=d["knowledge_base_id"],
                        file_hash=d["file_hash"],
                        filename=d["filename"],
                        content_type=d["content_type"],
                        provider=d["provider"],
                        priority=d["priority"],
                    )
                    logger.info(
                        f"Dispatching parse task for document {d['document_id']} (priority: {d['priority']}, provider: {d['provider']})"
                    )
                    kicker = handle_parse.kicker().with_labels(queue_name=get_queue_name(d["priority"]))
                    await kicker.kiq(msg)
                    dispatched_ids.append(d["document_id"])
            except Exception as exc:
                logger.error(f"Error occurred during Taskiq dispatch: {exc}")
                # Identify document IDs that failed to publish and revert their status to QUEUED
                failed_ids = [d["document_id"] for d in docs_to_dispatch if d["document_id"] not in dispatched_ids]
                if failed_ids:
                    logger.info(f"Reverting status of failed document(s) {failed_ids} back to QUEUED")
                    try:
                        async with AsyncTransaction() as session:
                            revert_stmt = (
                                update(KnowledgeBaseDocument)
                                .where(KnowledgeBaseDocument.id.in_(failed_ids))
                                .values(status="QUEUED")
                            )
                            await session.execute(revert_stmt)
                    except Exception as revert_exc:
                        logger.error(f"Failed to revert document statuses: {revert_exc}")
                raise exc

            # Progressive back-off sleep: reset on dispatch, backoff otherwise
            sleep_index = 0 if docs_to_dispatch else min(sleep_index + 1, len(SLEEP_INTERVALS) - 1)
            sleep_time = SLEEP_INTERVALS[sleep_index]
            await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error(f"Error in scheduling dispatcher loop: {exc}")
            await asyncio.sleep(5.0)

    logger.info("Stopped DB-polling scheduling dispatcher loop.")


async def start_dispatchers(broker: Any) -> None:
    """Start scheduling dispatchers."""
    global _dispatcher_task, _stop_event, _dispatcher_id
    _stop_event = asyncio.Event()
    _dispatcher_id = str(uuid4())  # Unique ID for this process's dispatcher
    _dispatcher_task = asyncio.create_task(
        dispatcher_loop(broker, _stop_event, _dispatcher_id),
        name="dispatcher_loop",
    )


async def stop_dispatchers() -> None:
    """Stop all running scheduling dispatcher tasks gracefully."""
    global _dispatcher_task, _stop_event
    if _stop_event:
        _stop_event.set()
    if _dispatcher_task:
        logger.info("Stopping scheduling dispatcher loop...")
        _dispatcher_task.cancel()
        await asyncio.gather(_dispatcher_task, return_exceptions=True)
        _dispatcher_task = None
        logger.info("All scheduling dispatcher loops stopped.")

    # Close connection pool
    await close_redis_client()
