from app.common.database import JSON_VARIANT
from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy.orm import Mapped, mapped_column


class SynonymMap(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "synonym_maps"

    keyword: Mapped[str] = mapped_column(unique=True, index=True, nullable=False)
    synonyms: Mapped[list[str]] = mapped_column(JSON_VARIANT, nullable=False)
    description: Mapped[str | None] = mapped_column(nullable=True)
