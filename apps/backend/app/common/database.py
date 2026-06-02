from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

JSON_VARIANT = JSON().with_variant(JSONB, "postgresql")
