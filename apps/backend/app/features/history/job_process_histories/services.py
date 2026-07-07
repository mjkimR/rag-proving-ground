from typing import Annotated

from app_layer_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
)
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.history.job_process_histories.models import JobProcessHistory
from app.features.history.job_process_histories.repos import JobProcessHistoryRepository
from app.features.history.job_process_histories.schemas import (
    JobProcessHistoryCreate,
)


class JobProcessHistoryContextKwargs(BaseContextKwargs):
    pass


class JobProcessHistoryService(
    BaseCreateServiceMixin[
        JobProcessHistoryRepository, JobProcessHistory, JobProcessHistoryCreate, JobProcessHistoryContextKwargs
    ],
    BaseGetMultiServiceMixin[JobProcessHistoryRepository, JobProcessHistory, JobProcessHistoryContextKwargs],
    BaseGetServiceMixin[JobProcessHistoryRepository, JobProcessHistory, JobProcessHistoryContextKwargs],
):
    def __init__(self, repo: Annotated[JobProcessHistoryRepository, Depends()]):
        self._repo = repo

    @property
    def repo(self) -> JobProcessHistoryRepository:
        return self._repo

    @property
    def context_model(self):
        return JobProcessHistoryContextKwargs

    async def record(self, session: AsyncSession, data: JobProcessHistoryCreate) -> JobProcessHistory:
        return await self.create(session, data)
