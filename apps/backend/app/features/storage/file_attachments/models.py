from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.features.storage.session_file_attachments.models import SessionFileAttachment


class FileAttachment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "file_attachments"

    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column()
    storage_path: Mapped[str] = mapped_column(String(512))

    # Relationships
    session_file_attachments: Mapped[list["SessionFileAttachment"]] = relationship(
        "SessionFileAttachment", back_populates="file_attachment", cascade="all, delete-orphan"
    )
