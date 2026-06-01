"""FastStream Redis broker singleton."""

from faststream.redis import RedisBroker
from rag_core.config import get_redis_settings


def create_broker() -> RedisBroker:
    settings = get_redis_settings()
    return RedisBroker(url=settings.url)


broker = create_broker()
