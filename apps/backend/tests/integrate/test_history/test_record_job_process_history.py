from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import pytest
from app.features.history.job_process_histories.repos import JobProcessHistoryRepository
from app.features.history.job_process_histories.services import JobProcessHistoryService
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.real_commit


async def test_job_process_history_persists_event(
    session: AsyncSession,
    make_db: Callable[..., Awaitable[Any]],
) -> None:
    service = JobProcessHistoryService(JobProcessHistoryRepository())
    resource_id = uuid4()

    history = await make_db(
        JobProcessHistoryRepository,
        resource_id=resource_id,
        stage="parsing",
        metrics={"element_count": 5},
    )

    persisted = await service.repo.get_by_pk(session, history.id)

    assert persisted is not None
    assert persisted.resource_id == resource_id
    assert persisted.stage == "parsing"
    assert persisted.metrics == {"element_count": 5}
