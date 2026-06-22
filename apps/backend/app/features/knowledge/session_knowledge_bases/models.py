from typing import TYPE_CHECKING
from uuid import UUID

from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.features.knowledge.knowledge_bases.models import KnowledgeBase


class SessionKnowledgeBase(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "session_knowledge_bases"
    __table_args__ = (UniqueConstraint("thread_id", "knowledge_base_id", name="uq_thread_knowledge_base"),)

    thread_id: Mapped[str] = mapped_column(String(255), index=True)
    knowledge_base_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"))

    # Relationships
    knowledge_base: Mapped["KnowledgeBase"] = relationship("KnowledgeBase", back_populates="session_knowledge_bases")
