from datetime import datetime
from typing import TYPE_CHECKING

from app.common.database import JSON_VARIANT
from app.features.knowledge.session_knowledge_bases.models import SessionKnowledgeBase
from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.features.knowledge.knowledge_base_documents.models import KnowledgeBaseDocument


class KnowledgeBase(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "knowledge_bases"
    name: Mapped[str] = mapped_column(unique=True)
    status: Mapped[str] = mapped_column(default="READY")
    embedding_config: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)
    embed_config_hash: Mapped[str | None] = mapped_column(nullable=True)
    default_chunking_config: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)
    default_parsing_config: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)
    is_temp: Mapped[bool] = mapped_column(default=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    documents: Mapped[list["KnowledgeBaseDocument"]] = relationship(
        "KnowledgeBaseDocument", back_populates="knowledge_base", cascade="all, delete-orphan"
    )
    session_knowledge_bases: Mapped[list["SessionKnowledgeBase"]] = relationship(
        "SessionKnowledgeBase", back_populates="knowledge_base", cascade="all, delete-orphan"
    )
