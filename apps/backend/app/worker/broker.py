"""Taskiq Redis broker configuration."""

from rag_core.config import get_redis_settings
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

settings = get_redis_settings()

# Configure Result Backend with 2-hour TTL (7200 seconds) to prevent memory leak
result_backend = RedisAsyncResultBackend(
    redis_url=settings.url,
    keep_results=True,
    result_ex_time=7200,
)

# Configure Redis List Broker
broker = ListQueueBroker(
    url=settings.url,
    result_backend=result_backend,
)
