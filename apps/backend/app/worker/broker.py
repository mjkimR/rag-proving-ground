from rag_core.config import get_rabbitmq_settings, get_redis_settings
from taskiq_aio_pika import AioPikaBroker, Queue
from taskiq_redis import RedisAsyncResultBackend

redis_settings = get_redis_settings()
rabbitmq_settings = get_rabbitmq_settings()

# Configure Result Backend with 2-hour TTL (7200 seconds) to prevent memory leak
result_backend = RedisAsyncResultBackend(
    redis_url=redis_settings.url,
    keep_results=True,
    result_ex_time=7200,
)

# Configure RabbitMQ Broker with isolated queues supporting native priority
broker = AioPikaBroker(
    url=rabbitmq_settings.url,
    result_backend=result_backend,
    task_queues=[
        Queue(name="taskiq", declare=True),
        Queue(
            name=rabbitmq_settings.parse_queue_name,
            declare=True,
            arguments={
                "x-queue-type": "classic",
                "x-max-priority": rabbitmq_settings.max_priority,
            },
        ),
        Queue(
            name=rabbitmq_settings.chunk_queue_name,
            declare=True,
            arguments={
                "x-queue-type": "classic",
                "x-max-priority": rabbitmq_settings.max_priority,
            },
        ),
        Queue(
            name=rabbitmq_settings.embed_queue_name,
            declare=True,
            arguments={
                "x-queue-type": "classic",
                "x-max-priority": rabbitmq_settings.max_priority,
            },
        ),
    ],
)
