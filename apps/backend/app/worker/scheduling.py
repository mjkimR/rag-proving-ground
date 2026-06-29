"""DB-polling staging queue and fair round-robin scheduling dispatchers."""

import asyncio
from typing import Any
from uuid import uuid4

import redis.asyncio as aioredis
from app.common.utils.time_util import get_current_time
from app.features.knowledge.knowledge_base_documents.schemas import ParseDocumentMessage
from loguru import logger
from rag_core.config import get_rabbitmq_settings, get_redis_settings

_redis_client: aioredis.Redis | None = None
_dispatcher_task: asyncio.Task | None = None
_cleanup_task: asyncio.Task | None = None
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


async def get_queue_message_count(
    connection: Any,
    channel: Any,
    url: str,
    queue_name: str,
) -> tuple[Any, Any, int]:
    """Retrieve or reuse RabbitMQ connection/channel, and return message count of the queue.

    If a connection or channel is closed or None, a new one is robustly created.
    If the passive queue declaration fails, the channel is closed automatically by the broker,
    and we reset the channel to None.
    """
    import aio_pika

    if connection is None or connection.is_closed:
        connection = await aio_pika.connect_robust(url)
        channel = None
    if channel is None or channel.is_closed:
        channel = await connection.channel()

    try:
        q = await channel.declare_queue(queue_name, passive=True)
        message_count = q.declaration_result.message_count or 0
    except Exception:
        # If queue does not exist, channel is closed automatically. Reset channel to None.
        channel = None
        message_count = 0

    return connection, channel, message_count


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
    rabbitmq_connection = None
    rabbitmq_channel = None
    try:
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

                # 2. Check the total number of waiting tasks in RabbitMQ priority queue
                total_waiting = 0
                try:
                    rabbitmq_settings = get_rabbitmq_settings()
                    rabbitmq_connection, rabbitmq_channel, total_waiting = await get_queue_message_count(
                        rabbitmq_connection,
                        rabbitmq_channel,
                        rabbitmq_settings.url,
                        rabbitmq_settings.parse_queue_name,
                    )
                except Exception as exc:
                    logger.error(f"Error checking RabbitMQ queue length: {exc}")

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
                        .where(
                            KnowledgeBaseDocument.id.in_(select(candidates_cte.c.id).where(candidates_cte.c.rn == 1))
                        )
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
                                    "content_type": doc.document_info.get("content_type")
                                    if doc.document_info
                                    else None,
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
                        from app.features.knowledge.knowledge_base_documents.schemas import map_priority_to_int

                        kicker = handle_parse.kicker().with_labels(
                            queue_name=get_queue_name(d["priority"]),
                            priority=map_priority_to_int(d["priority"]),
                        )
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
    finally:
        from contextlib import suppress

        if rabbitmq_channel is not None and not rabbitmq_channel.is_closed:
            logger.info("Closing persistent RabbitMQ channel in scheduling dispatcher loop...")
            with suppress(Exception):
                await rabbitmq_channel.close()
        if rabbitmq_connection is not None and not rabbitmq_connection.is_closed:
            logger.info("Closing persistent RabbitMQ connection in scheduling dispatcher loop...")
            with suppress(Exception):
                await rabbitmq_connection.close()

    logger.info("Stopped DB-polling scheduling dispatcher loop.")


async def cleanup_loop(stop_event: asyncio.Event, dispatcher_id: str) -> None:
    """Background loop that periodically (every 30 seconds check, but actual execution every 30 minutes)

    cleans up expired temporary knowledge bases and orphaned raw file attachments.
    """
    logger.info(f"Starting background resource cleanup loop (ID: {dispatcher_id})...")
    from datetime import timedelta

    import sqlalchemy as sa
    from app.features.knowledge.knowledge_base_documents.models import KnowledgeBaseDocument
    from app.features.knowledge.knowledge_base_documents.usecases.crud import (
        KnowledgeDocumentCleanupTarget,
        cleanup_knowledge_document_assets,
    )
    from app.features.knowledge.knowledge_base_pages.models import KnowledgeBasePage
    from app.features.knowledge.knowledge_bases.models import KnowledgeBase
    from app.features.knowledge.session_knowledge_bases.models import SessionKnowledgeBase
    from app.features.storage.file_attachments.models import FileAttachment
    from app.features.storage.session_file_attachments.models import SessionFileAttachment
    from app_file_storage import get_storage_client
    from app_layer_base.core.database.transaction import AsyncTransaction
    from sqlalchemy import select

    while not stop_event.is_set():
        try:
            redis_client = await get_redis_client()
            lock_key = "lock:cleanup"

            # 1. Leader election / Lock check
            current_holder_bytes = await redis_client.get(lock_key)
            current_holder = (
                current_holder_bytes.decode("utf-8")
                if isinstance(current_holder_bytes, bytes)
                else current_holder_bytes
            )

            if current_holder is None:
                acquired = await redis_client.set(lock_key, dispatcher_id, ex=15, nx=True)
                if not acquired:
                    await asyncio.sleep(10.0)
                    continue
            elif current_holder != dispatcher_id:
                await asyncio.sleep(10.0)
                continue
            else:
                await redis_client.expire(lock_key, 15)

            # 2. Check if we should run the cleanup now
            run_lock_key = "lock:cleanup_last_run"
            already_run = await redis_client.get(run_lock_key)
            if already_run is not None:
                await asyncio.sleep(10.0)
                continue

            # Acquire the run lock for 30 minutes (1800 seconds)
            await redis_client.set(run_lock_key, "1", ex=1800)
            logger.info("Leader running periodic cleanup check...")

            # 3. Clean up expired temporary KnowledgeBases
            now = get_current_time()
            async with AsyncTransaction() as session:
                stmt = select(KnowledgeBase).where(
                    KnowledgeBase.is_temp,
                    KnowledgeBase.expires_at <= now,
                )
                result = await session.execute(stmt)
                expired_kbs = result.scalars().all()

                for kb in expired_kbs:
                    logger.info(f"Purging expired temporary KnowledgeBase: {kb.id} (name: {kb.name})")

                    # Get thread_id
                    skb_stmt = select(SessionKnowledgeBase).where(SessionKnowledgeBase.knowledge_base_id == kb.id)
                    skb_res = await session.execute(skb_stmt)
                    skb = skb_res.scalars().first()
                    thread_id = skb.thread_id if skb else None

                    # Get all documents in this KB
                    docs_stmt = select(KnowledgeBaseDocument).where(KnowledgeBaseDocument.knowledge_base_id == kb.id)
                    docs_res = await session.execute(docs_stmt)
                    docs = docs_res.scalars().all()

                    # Purge each document's assets (MinIO, Qdrant vectors) and database records
                    for doc in docs:
                        logger.info(f"Purging assets for document {doc.id}")
                        target = KnowledgeDocumentCleanupTarget(
                            document_id=doc.id,
                            file_hash=doc.file_hash,
                            knowledge_base_name=kb.name,
                            embed_config_hash=kb.embed_config_hash,
                        )
                        # Delete storage files & Qdrant vectors
                        await cleanup_knowledge_document_assets(target)

                        # Delete pages
                        await session.execute(
                            sa.delete(KnowledgeBasePage).where(KnowledgeBasePage.document_id == doc.id)
                        )
                        await session.delete(doc)

                    # Delete session mapping
                    await session.execute(
                        sa.delete(SessionKnowledgeBase).where(SessionKnowledgeBase.knowledge_base_id == kb.id)
                    )

                    # Delete SessionFileAttachments for the thread
                    if thread_id:
                        logger.info(f"Deleting session attachments for thread: {thread_id}")
                        await session.execute(
                            sa.delete(SessionFileAttachment).where(SessionFileAttachment.thread_id == thread_id)
                        )

                    # Finally delete the KB itself
                    await session.delete(kb)
                    logger.info(f"Purged temporary KnowledgeBase {kb.id}")

            # 4. Clean up orphaned raw file attachments older than 24 hours
            cutoff = get_current_time() - timedelta(hours=24)
            async with AsyncTransaction() as session:
                attachments_stmt = select(FileAttachment).where(FileAttachment.created_at <= cutoff)
                attachments_res = await session.execute(attachments_stmt)
                attachments = attachments_res.scalars().all()

                for fa in attachments:
                    # Check if bound to any session
                    sfa_check = await session.execute(
                        select(SessionFileAttachment).where(SessionFileAttachment.file_attachment_id == fa.id)
                    )
                    if sfa_check.scalars().first():
                        continue

                    # Check if referenced by any document
                    kbd_check = await session.execute(
                        select(KnowledgeBaseDocument).where(KnowledgeBaseDocument.file_hash == fa.sha256)
                    )
                    if kbd_check.scalars().first():
                        continue

                    logger.info(f"Purging orphaned raw file attachment: {fa.id} (sha256: {fa.sha256})")

                    # Delete from MinIO
                    try:
                        storage_client = get_storage_client()
                        await storage_client.delete_file(fa.storage_path)
                    except Exception as e:
                        logger.warning(f"Failed to delete orphaned file {fa.storage_path} from MinIO: {e}")

                    # Delete from DB
                    await session.delete(fa)

            await asyncio.sleep(10.0)

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error(f"Error in cleanup scheduler loop: {exc}")
            await asyncio.sleep(10.0)

    logger.info("Stopped background resource resource cleanup loop.")


async def start_dispatchers(broker: Any) -> None:
    """Start scheduling dispatchers and cleanup loops."""
    global _dispatcher_task, _cleanup_task, _stop_event, _dispatcher_id
    _stop_event = asyncio.Event()
    _dispatcher_id = str(uuid4())  # Unique ID for this process's dispatcher
    _dispatcher_task = asyncio.create_task(
        dispatcher_loop(broker, _stop_event, _dispatcher_id),
        name="dispatcher_loop",
    )
    _cleanup_task = asyncio.create_task(
        cleanup_loop(_stop_event, _dispatcher_id),
        name="cleanup_loop",
    )


async def stop_dispatchers() -> None:
    """Stop all running scheduling dispatcher and cleanup tasks gracefully."""
    global _dispatcher_task, _cleanup_task, _stop_event
    if _stop_event:
        _stop_event.set()

    tasks_to_cancel = []
    if _dispatcher_task:
        logger.info("Stopping scheduling dispatcher loop...")
        _dispatcher_task.cancel()
        tasks_to_cancel.append(_dispatcher_task)
    if _cleanup_task:
        logger.info("Stopping cleanup loop...")
        _cleanup_task.cancel()
        tasks_to_cancel.append(_cleanup_task)

    if tasks_to_cancel:
        await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
        _dispatcher_task = None
        _cleanup_task = None
        logger.info("All scheduling dispatcher and cleanup loops stopped.")

    # Close connection pool
    await close_redis_client()
