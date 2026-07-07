"""Task dispatch port for feature use cases.

Features must not import worker handlers (import direction: worker -> features only).
AsyncKicker publishes by task name through the shared broker, so enqueueing a task
does not require loading any handler module.
"""

from typing import Any

from taskiq.kicker import AsyncKicker

from app.worker.broker import broker

PARSE_DOCUMENT_TASK = "parse_document"
CHUNK_DOCUMENT_TASK = "chunk_document"
EMBED_DOCUMENT_TASK = "embed_document"
PROCESS_FILE_ATTACHMENT_TASK = "process_file_attachment"


async def kick_task(
    task_name: str,
    *args: Any,
    queue_name: str | None = None,
    priority: int | None = None,
    **kwargs: Any,
) -> Any:
    """Enqueues a worker task by name and returns the taskiq task handle."""
    kicker: AsyncKicker[Any, Any] = AsyncKicker(task_name=task_name, broker=broker, labels={})
    labels: dict[str, Any] = {}
    if queue_name is not None:
        labels["queue_name"] = queue_name
    if priority is not None:
        labels["priority"] = priority
    if labels:
        kicker = kicker.with_labels(**labels)
    return await kicker.kiq(*args, **kwargs)
