from typing import Annotated

from app_layer_base.base.usecases.crud import (
    BaseGetMultiUseCase,
    BaseGetUseCase,
)
from fastapi import Depends

from app.features.history.job_process_histories.models import JobProcessHistory
from app.features.history.job_process_histories.services import JobProcessHistoryContextKwargs, JobProcessHistoryService


class GetJobProcessHistoryUseCase(
    BaseGetUseCase[JobProcessHistoryService, JobProcessHistory, JobProcessHistoryContextKwargs]
):
    def __init__(self, service: Annotated[JobProcessHistoryService, Depends()]) -> None:
        super().__init__(service)


class GetMultiJobProcessHistoryUseCase(
    BaseGetMultiUseCase[JobProcessHistoryService, JobProcessHistory, JobProcessHistoryContextKwargs]
):
    def __init__(self, service: Annotated[JobProcessHistoryService, Depends()]) -> None:
        super().__init__(service)
