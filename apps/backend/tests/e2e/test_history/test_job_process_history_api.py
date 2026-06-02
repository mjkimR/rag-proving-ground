from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import pytest
from app.features.history.job_process_histories.repos import JobProcessHistoryRepository
from httpx import AsyncClient

from tests.utils import assert_status_code

pytestmark = pytest.mark.real_commit


async def test_job_process_history_filters_by_resource_stage_and_outcome(
    client: AsyncClient,
    make_db: Callable[..., Awaitable[Any]],
) -> None:
    resource_id = uuid4()
    target = await make_db(
        JobProcessHistoryRepository,
        resource_type="knowledge_base_document",
        resource_id=resource_id,
        stage="chunking",
        outcome="SUCCESS",
        metrics={"chunk_count": 3},
    )
    await make_db(
        JobProcessHistoryRepository,
        resource_type="knowledge_base_document",
        resource_id=uuid4(),
        stage="embedding",
        outcome="FAILED",
    )

    response = await client.get(
        "/api/v1/job_process_histories",
        params={
            "resource_type": "knowledge_base_document",
            "resource_id": str(resource_id),
            "stage": "chunking",
            "outcome": "SUCCESS",
        },
    )

    assert_status_code(response, 200)
    data = response.json()
    assert data["total_count"] == 1
    assert data["items"][0]["id"] == str(target.id)
    assert data["items"][0]["metrics"] == {"chunk_count": 3}


async def test_job_process_history_get_by_id(client: AsyncClient, make_db: Callable[..., Awaitable[Any]]) -> None:
    history = await make_db(
        JobProcessHistoryRepository,
        name="Parse success",
    )

    response = await client.get(f"/api/v1/job_process_histories/{history.id}")

    assert_status_code(response, 200)
    assert response.json()["name"] == "Parse success"
