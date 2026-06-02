from app.features.history.job_process_histories.schemas import JobProcessHistoryCreate
from polyfactory.factories.pydantic_factory import ModelFactory


class JobProcessHistoryCreateFactory(ModelFactory):
    __model__ = JobProcessHistoryCreate

    config = None
    metrics = None
