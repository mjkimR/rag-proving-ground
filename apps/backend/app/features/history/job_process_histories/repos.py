from app.features.history.job_process_histories.models import JobProcessHistory
from app.features.history.job_process_histories.schemas import (
    JobProcessHistoryCreate,
    JobProcessHistoryPatch,
    JobProcessHistoryPut,
)
from app_layer_base.base.repos.base import BaseRepository


class JobProcessHistoryRepository(
    BaseRepository[JobProcessHistory, JobProcessHistoryCreate, JobProcessHistoryPut, JobProcessHistoryPatch]
):
    model = JobProcessHistory
