from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from app.features.history.job_process_histories.api.v1 import (
    get_job_process_histories,
    get_job_process_history,
    router,
)
from app.features.history.job_process_histories.models import JobProcessHistory
from app.features.history.job_process_histories.repos import JobProcessHistoryRepository
from app.features.history.job_process_histories.schemas import JobProcessHistoryCreate
from app.features.history.job_process_histories.services import JobProcessHistoryService
from app.features.history.job_process_histories.usecases.crud import (
    GetJobProcessHistoryUseCase,
    GetMultiJobProcessHistoryUseCase,
)
from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.schemas.paginated import PaginatedList
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession


def test_job_process_history_router_exposes_only_read_methods() -> None:
    route_methods = {
        method for route in router.routes if isinstance(route, APIRoute) for method in (route.methods or [])
    }

    assert route_methods == {"GET"}


async def test_get_job_process_histories_returns_paginated_results_with_filters() -> None:
    from app_layer_base.base.repos.query_options import ListQueryOptions

    class FakeUseCase:
        service = SimpleNamespace(repo=SimpleNamespace(model=JobProcessHistory))

        def __init__(self) -> None:
            self.query_options = None

        async def execute(self, query_options):
            self.query_options = query_options
            return PaginatedList(items=[], total_count=0, offset=query_options.offset, limit=query_options.limit)

    use_case = FakeUseCase()
    resource_id = uuid4()

    query_options = ListQueryOptions(
        offset=10,
        limit=20,
        where=(
            JobProcessHistory.resource_type == "knowledge_base_document",
            JobProcessHistory.resource_id == resource_id,
            JobProcessHistory.stage == "parsing",
            JobProcessHistory.outcome == "SUCCESS",
        ),
    )

    result = await get_job_process_histories(
        use_case=cast(GetMultiJobProcessHistoryUseCase, use_case),
        query_options=query_options,
    )

    assert result.total_count == 0
    assert result.offset == 10
    assert result.limit == 20
    assert use_case.query_options is not None
    assert len(use_case.query_options.where) == 4


async def test_get_job_process_history_returns_one_history_row() -> None:
    history_id = uuid4()
    history = SimpleNamespace(id=history_id)
    use_case = SimpleNamespace(execute=lambda job_process_history_id: _async_return(history))

    result = await get_job_process_history(
        use_case=cast(GetJobProcessHistoryUseCase, use_case), job_process_history_id=history_id
    )

    assert result is history


async def test_get_job_process_history_missing_row_returns_404() -> None:
    use_case = SimpleNamespace(execute=lambda job_process_history_id: _async_return(None))

    with pytest.raises(NotFoundException):
        await get_job_process_history(
            use_case=cast(GetJobProcessHistoryUseCase, use_case), job_process_history_id=uuid4()
        )


async def test_job_process_history_service_record_creates_history_row() -> None:
    class FakeRepo:
        async def create(self, session, obj_in, **update_fields):
            self.session = session
            self.obj_in = obj_in
            self.update_fields = update_fields
            return SimpleNamespace(id=uuid4(), **obj_in.model_dump())

    repo = FakeRepo()
    service = JobProcessHistoryService(repo=cast(JobProcessHistoryRepository, repo))
    session = cast(AsyncSession, object())
    resource_id = uuid4()
    data = JobProcessHistoryCreate(
        resource_type="knowledge_base_document",
        resource_id=resource_id,
        stage="parsing",
        outcome="SUCCESS",
        provider="docling",
        config={"provider": "docling"},
        metrics={"element_count": 3, "cache_hit": False},
        duration_seconds=1.25,
    )

    result = await service.record(session, data)

    assert repo.session is session
    assert repo.obj_in is data
    assert result.resource_type == "knowledge_base_document"
    assert result.resource_id == resource_id
    assert result.stage == "parsing"
    assert result.outcome == "SUCCESS"
    assert result.metrics == {"element_count": 3, "cache_hit": False}


async def _async_return(value):
    return value
