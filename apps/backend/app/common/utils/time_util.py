from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def get_current_time() -> datetime:
    return datetime.now(UTC)


def get_current_time_in_tz(tz: ZoneInfo) -> datetime:
    return datetime.now(tz)
