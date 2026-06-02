from uuid import UUID

from app.common.database import JSON_VARIANT
from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import Index
from sqlalchemy.orm import Mapped, mapped_column


class JobProcessHistory(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "job_process_histories"
    __table_args__ = (
        Index("ix_job_process_histories_resource", "resource_type", "resource_id"),
        Index("ix_job_process_histories_stage", "stage"),
        Index("ix_job_process_histories_outcome", "outcome"),
        Index("ix_job_process_histories_created_at", "created_at"),
    )

    name: Mapped[str | None] = mapped_column(nullable=True)
    resource_type: Mapped[str] = mapped_column()
    resource_id: Mapped[UUID] = mapped_column()
    stage: Mapped[str] = mapped_column()
    outcome: Mapped[str] = mapped_column()
    provider: Mapped[str | None] = mapped_column(nullable=True)
    model_name: Mapped[str | None] = mapped_column(nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)
    error_message: Mapped[str | None] = mapped_column(nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(nullable=True)
