from typing import TYPE_CHECKING
from uuid import UUID

from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.features.knowledge.knowledge_bases.models import KnowledgeBase
    from app.features.knowledge.knowledge_chunking_histories.models import KnowledgeChunkingHistory
    from app.features.knowledge.knowledge_embedding_histories.models import KnowledgeEmbeddingHistory
    from app.features.knowledge.knowledge_parsing_histories.models import KnowledgeParsingHistory


class KnowledgeBaseDocument(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "knowledge_base_documents"
    name: Mapped[str] = mapped_column()
    knowledge_base_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(default="READY")
    file_hash: Mapped[str] = mapped_column()
    document_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parsing_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    chunking_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    knowledge_base: Mapped["KnowledgeBase"] = relationship("KnowledgeBase", back_populates="documents")
    parsing_histories: Mapped[list["KnowledgeParsingHistory"]] = relationship(
        "KnowledgeParsingHistory", back_populates="document", cascade="all, delete-orphan"
    )
    chunking_histories: Mapped[list["KnowledgeChunkingHistory"]] = relationship(
        "KnowledgeChunkingHistory", back_populates="document", cascade="all, delete-orphan"
    )
    embedding_histories: Mapped[list["KnowledgeEmbeddingHistory"]] = relationship(
        "KnowledgeEmbeddingHistory", back_populates="document", cascade="all, delete-orphan"
    )
