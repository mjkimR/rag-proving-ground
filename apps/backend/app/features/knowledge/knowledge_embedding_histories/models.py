from typing import TYPE_CHECKING
from uuid import UUID

from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.features.knowledge.knowledge_base_documents.models import KnowledgeBaseDocument


class KnowledgeEmbeddingHistory(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "knowledge_embedding_histories"
    name: Mapped[str | None] = mapped_column(nullable=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_base_documents.id", ondelete="CASCADE"))
    model_name: Mapped[str] = mapped_column()
    vector_count: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column()
    embedding_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(nullable=True)

    # Relationships
    document: Mapped["KnowledgeBaseDocument"] = relationship(
        "KnowledgeBaseDocument", back_populates="embedding_histories"
    )
