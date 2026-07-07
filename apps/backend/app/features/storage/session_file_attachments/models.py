from typing import TYPE_CHECKING
from uuid import UUID

from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.database import JSON_VARIANT

if TYPE_CHECKING:
    from app.features.storage.file_attachments.models import FileAttachment


class SessionFileAttachment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "session_file_attachments"
    __table_args__ = (UniqueConstraint("thread_id", "file_attachment_id", name="uq_thread_file_attachment"),)

    thread_id: Mapped[str] = mapped_column(String(255), index=True)
    file_attachment_id: Mapped[UUID] = mapped_column(ForeignKey("file_attachments.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(nullable=True)
    processed_metadata: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)

    # Relationships
    file_attachment: Mapped["FileAttachment"] = relationship(
        "FileAttachment", back_populates="session_file_attachments"
    )
