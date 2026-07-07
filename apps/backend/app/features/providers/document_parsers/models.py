from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy.orm import Mapped, mapped_column

from app.common.database import JSON_VARIANT


class DocumentParser(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "document_parsers"
    name: Mapped[str] = mapped_column(unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_default: Mapped[bool] = mapped_column(default=False)
    connection_info: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)
    extra_metadata: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)
