from typing import Annotated
from uuid import UUID

from app.features.history.job_process_histories.query_options import get_job_process_histories_query_options
from app.features.history.job_process_histories.schemas import JobProcessHistoryRead
from app.features.history.job_process_histories.usecases.crud import (
    GetJobProcessHistoryUseCase,
    GetMultiJobProcessHistoryUseCase,
)
from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.schemas.paginated import PaginatedList
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/job_process_histories", tags=["JobProcessHistory"], dependencies=[])


@router.get("", response_model=PaginatedList[JobProcessHistoryRead])
async def get_job_process_histories(
    use_case: Annotated[GetMultiJobProcessHistoryUseCase, Depends()],
    query_options: Annotated[ListQueryOptions, Depends(get_job_process_histories_query_options)],
):
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
