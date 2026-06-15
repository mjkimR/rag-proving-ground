"""Redis-based staging queue and fair round-robin scheduling dispatchers."""

import asyncio
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
from app.features.knowledge.knowledge_base_documents.schemas import ParseDocumentMessage
from faststream.redis import RedisBroker
from loguru import logger
from rag_core.config import get_redis_settings

# Global Redis client instance
_redis_client: aioredis.Redis | None = None

MAX_DISPATCH_RETRIES = 3


async def get_redis_client() -> aioredis.Redis:
    """Return the global Redis client instance, initializing it if necessary."""
    global _redis_client
    if _redis_client is None:
        settings = get_redis_settings()
        _redis_client = aioredis.from_url(
            settings.url,
            encoding="utf-8",
            decode_responses=False,
            max_connections=20,
        )
    return _redis_client


async def close_redis_client() -> None:
    """Close the global Redis client."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


# Lua script to guarantee atomic enqueueing of messages
LUA_ENQUEUE_SCRIPT = """
local active_kbs_key = KEYS[1]
local active_queues_key = KEYS[2]
local kb_queue_key = KEYS[3]
local kb_id = ARGV[1]
local msg_json = ARGV[2]

local is_new = redis.call("SADD", active_kbs_key, kb_id)
if is_new == 1 then
    redis.call("RPUSH", active_queues_key, kb_id)
end
redis.call("RPUSH", kb_queue_key, msg_json)
return 1
"""


async def enqueue_parse_document_message(
    knowledge_base_id: UUID,
    msg: ParseDocumentMessage,
    provider: str,
) -> None:
    """Enqueue a parse message to the Redis staging queue atomically using a Lua script."""
    client = await get_redis_client()
    redis: Any = client
    try:
        msg_json = msg.model_dump_json()
        kb_str = str(knowledge_base_id)

        active_kbs_key = f"active_kbs:{provider}"
        active_queues_key = f"active_queues:{provider}"
        kb_queue_key = f"kb_queue:{kb_str}:{provider}"

        # Execute atomic Lua script
        await redis.eval(
            LUA_ENQUEUE_SCRIPT,
            3,
            active_kbs_key,
            active_queues_key,
            kb_queue_key,
            kb_str,
            msg_json,
        )
        logger.info(f"Atomically enqueued document {msg.document_id} for KB {kb_str} to staging queue '{provider}'")
    except Exception as exc:
        logger.error(f"Failed to enqueue message to Redis staging queue for KB {knowledge_base_id}: {exc}")
        raise exc


async def dispatcher_loop(
    provider: str,
    broker: RedisBroker,
    stop_event: asyncio.Event,
) -> None:
    """Background dispatcher loop that pops staging messages in round-robin and publishes them with At-Least-Once guarantee."""
    logger.info(f"Starting scheduling dispatcher loop for provider: {provider}")
    client = await get_redis_client()
    redis: Any = client

    from rag_core.adapters.parser.registry import ParserRegistry

    active_providers = ParserRegistry.list_parsers()

    while not stop_event.is_set():
        try:
            # 1. Pop the next active KB from the round-robin queue
            kb_id_bytes = await redis.lpop(f"active_queues:{provider}")
            if not kb_id_bytes:
                # Staging queue is empty, sleep to avoid high CPU/Redis polling
                await asyncio.sleep(0.5)
                continue

            kb_str = kb_id_bytes.decode("utf-8") if isinstance(kb_id_bytes, bytes) else kb_id_bytes

            main_key = f"kb_queue:{kb_str}:{provider}"
            processing_key = f"kb_queue:{kb_str}:{provider}:processing"
            retry_key = f"retry_counter:{kb_str}:{provider}"

            success = False
            try:
                # 2. Atomically move the head message from the main queue into the processing
                #    queue (Reliable Queue pattern — safe across multiple worker processes)
                msg_bytes = await redis.lmove(main_key, processing_key, "LEFT", "RIGHT")
                if not msg_bytes:
                    # Main queue is empty (out of sync), clean up active set
                    await redis.srem(f"active_kbs:{provider}", kb_str)
                    continue

                # 3. Publish to FastStream broker
                msg_json = msg_bytes.decode("utf-8") if isinstance(msg_bytes, bytes) else msg_bytes
                msg = ParseDocumentMessage.model_validate_json(msg_json)

                # Route to dynamic provider-specific queue or fallback based on active registry
                queue_name = f"document.parse.{provider}" if provider in active_providers else "document.parse"

                logger.debug(
                    f"Dispatcher dispatching message for doc {msg.document_id} from KB {kb_str} to {queue_name}"
                )
                await broker.publish(msg, queue_name)

                # 4. Successfully published: remove from processing queue and clear distributed retry counter
                await redis.lpop(processing_key)
                await redis.delete(retry_key)
                success = True

            except Exception as exc:
                logger.error(f"Error dispatching message for KB {kb_str} (will retry): {exc}")

                # Atomically increment the shared retry counter in Redis so all worker processes
                # contribute to the same failure tally (unlike an in-memory dict).
                fail_count = await redis.incr(retry_key)

                if fail_count >= MAX_DISPATCH_RETRIES:
                    # Max retries exceeded: isolate the message to DLQ
                    logger.warning(
                        f"KB {kb_str} exceeded {MAX_DISPATCH_RETRIES} retries, "
                        f"isolating to DLQ for provider '{provider}'"
                    )
                    try:
                        await redis.lmove(processing_key, f"dlq:{provider}", "LEFT", "RIGHT")
                        await redis.delete(retry_key)
                        await redis.srem(f"active_kbs:{provider}", kb_str)
                    except Exception as redis_exc:
                        # If the DLQ move itself fails (e.g. Redis network blip), the message
                        # remains stranded in processing_key. A periodic recovery scan of
                        # 'kb_queue:*:processing' keys is required to drain such orphans.
                        logger.critical(
                            f"Failed to isolate KB {kb_str} to DLQ: {redis_exc}. "
                            f"Message is stranded in '{processing_key}' and requires manual recovery."
                        )
                else:
                    # Restore the message to the head of the main queue and re-schedule the KB
                    try:
                        await redis.lmove(processing_key, main_key, "LEFT", "LEFT")
                        await redis.rpush(f"active_queues:{provider}", kb_str)
                    except Exception as redis_exc:
                        # If the restore lmove fails, the message is stranded in processing_key.
                        # The retry counter is already incremented, so it will trend toward DLQ.
                        logger.critical(
                            f"Failed to restore KB {kb_str} message from processing queue: {redis_exc}. "
                            f"Message is stranded in '{processing_key}' and requires manual recovery."
                        )
                    else:
                        await asyncio.sleep(1.0)
                continue

            # 5. Check if there are more messages left in this KB's main queue
            if success:
                queue_len = await redis.llen(main_key)
                if queue_len > 0:
                    # Still has messages: push it back to the end of the round-robin list
                    await redis.rpush(f"active_queues:{provider}", kb_str)
                else:
                    # Empty: remove from active set
                    await redis.srem(f"active_kbs:{provider}", kb_str)

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error(f"Error in dispatcher loop for provider {provider}: {exc}")
            await asyncio.sleep(1.0)

    logger.info(f"Stopped scheduling dispatcher loop for provider: {provider}")


_dispatcher_tasks: list[asyncio.Task] = []
_stop_event: asyncio.Event | None = None


async def start_dispatchers(broker: RedisBroker) -> None:
    """Start scheduling dispatchers for all registered parser providers."""
    global _dispatcher_tasks, _stop_event

    from rag_core.adapters.parser.providers import register_default_parsers
    from rag_core.adapters.parser.registry import ParserRegistry

    register_default_parsers()
    providers = ParserRegistry.list_parsers()  # e.g., ["docling", "native_text"]

    _stop_event = asyncio.Event()
    _dispatcher_tasks = []

    for provider in providers:
        task = asyncio.create_task(
            dispatcher_loop(provider, broker, _stop_event),
            name=f"dispatcher_{provider}",
        )
        _dispatcher_tasks.append(task)


async def stop_dispatchers() -> None:
    """Stop all running scheduling dispatcher tasks gracefully and close connection pool."""
    global _dispatcher_tasks, _stop_event
    if _stop_event:
        _stop_event.set()
    if _dispatcher_tasks:
        logger.info("Stopping scheduling dispatcher loops...")
        for task in _dispatcher_tasks:
            task.cancel()
        await asyncio.gather(*_dispatcher_tasks, return_exceptions=True)
        _dispatcher_tasks = []
        logger.info("All scheduling dispatcher loops stopped.")

    # Close connection pool
    await close_redis_client()
