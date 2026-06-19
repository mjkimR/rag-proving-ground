from typing import TYPE_CHECKING
from uuid import UUID

from app.common.database import JSON_VARIANT
from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.features.knowledge.knowledge_base_pages.models import KnowledgeBasePage
    from app.features.knowledge.knowledge_bases.models import KnowledgeBase


class KnowledgeBaseDocument(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "knowledge_base_documents"
    name: Mapped[str] = mapped_column()
    knowledge_base_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(default="READY")
    priority: Mapped[str] = mapped_column(default="medium")
    file_hash: Mapped[str] = mapped_column()
    document_info: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)
    parsing_config: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)
    chunking_config: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)

    # Relationships
    knowledge_base: Mapped["KnowledgeBase"] = relationship("KnowledgeBase", back_populates="documents")
    pages: Mapped[list["KnowledgeBasePage"]] = relationship(
        "KnowledgeBasePage", back_populates="document", cascade="all, delete-orphan"
    )
