from typing import TYPE_CHECKING
from uuid import UUID

from app.common.database import JSON_VARIANT
from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.features.knowledge.knowledge_base_documents.models import KnowledgeBaseDocument


class KnowledgeBasePage(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "knowledge_base_pages"

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_base_documents.id", ondelete="CASCADE"), nullable=False
    )
    page_id: Mapped[str] = mapped_column(unique=True, nullable=False)
    page_number: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(nullable=False)
    metadata_info: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)

    # Relationships
    document: Mapped["KnowledgeBaseDocument"] = relationship("KnowledgeBaseDocument", back_populates="pages")
