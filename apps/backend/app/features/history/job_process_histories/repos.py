from app_layer_base.base.repos.base import BaseRepository

from app.features.history.job_process_histories.models import JobProcessHistory
from app.features.history.job_process_histories.schemas import (
    JobProcessHistoryCreate,
    JobProcessHistoryPatch,
    JobProcessHistoryPut,
)


class JobProcessHistoryRepository(
    BaseRepository[JobProcessHistory, JobProcessHistoryCreate, JobProcessHistoryPut, JobProcessHistoryPatch]
):
    model = JobProcessHistory
