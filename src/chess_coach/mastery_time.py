"""UTC clock and evidence-time validation for mastery."""

from __future__ import annotations

from datetime import UTC, datetime


def as_utc(value: datetime | None) -> datetime:
    current = value if value is not None else datetime.now(UTC)
    if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("as_of must be a timezone-aware datetime")
    return current.astimezone(UTC)


def parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(UTC)
    except (ValueError, OverflowError):
        return None
