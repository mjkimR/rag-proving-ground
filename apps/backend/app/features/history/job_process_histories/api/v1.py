from typing import Annotated
from uuid import UUID

from app.features.history.job_process_histories.schemas import JobProcessHistoryRead
from app.features.history.job_process_histories.usecases.crud import (
    GetJobProcessHistoryUseCase,
    GetMultiJobProcessHistoryUseCase,
)
from app_layer_base.base.deps.params.page import PaginationParam
from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.schemas.paginated import PaginatedList
from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/job_process_histories", tags=["JobProcessHistory"], dependencies=[])


@router.get("", response_model=PaginatedList[JobProcessHistoryRead])
async def get_job_process_histories(
    use_case: Annotated[GetMultiJobProcessHistoryUseCase, Depends()],
    pagination: PaginationParam,
    resource_type: Annotated[str | None, Query()] = None,
    resource_id: Annotated[UUID | None, Query()] = None,
    stage: Annotated[str | None, Query()] = None,
    outcome: Annotated[str | None, Query()] = None,
):
    model = use_case.service.repo.model
    where = []
    if resource_type is not None:
        where.append(model.resource_type == resource_type)
    if resource_id is not None:
        where.append(model.resource_id == resource_id)
    if stage is not None:
        where.append(model.stage == stage)
    if outcome is not None:
        where.append(model.outcome == outcome)

    query_options = ListQueryOptions(offset=pagination.offset, limit=pagination.limit, where=tuple(where))
    return await use_case.execute(query_options=query_options)


@router.get("/{job_process_history_id}", response_model=JobProcessHistoryRead)
async def get_job_process_history(
    use_case: Annotated[GetJobProcessHistoryUseCase, Depends()],
    job_process_history_id: UUID,
):
    job_process_history = await use_case.execute(job_process_history_id)
    if not job_process_history:
        raise NotFoundException()
    return job_process_history
