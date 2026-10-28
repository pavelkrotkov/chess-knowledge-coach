"""Extract server-requested cooldowns from retryable responses."""

from datetime import UTC, datetime, timedelta

from .db import Database
from .lichess_retry import header_delay
from .pipeline_cooldown import utc_now
from .pipeline_cooldown_storage import persist_deadline


def requested_delay(value, timestamp):
    if value is not None:
        digits = value.strip()
        if digits.isascii() and digits.isdigit() and len(digits.lstrip("0")) > 12:
            return float("inf")
    return header_delay(value, timestamp)


def observe_response(db: Database, response, clock) -> None:
    now = utc_now(clock)
    requested = requested_delay(response.headers.get("Retry-After"), now.timestamp())
    if response.status_code == 429:
        requested = max(60.0, requested or 0.0)
    elif response.status_code < 500 or requested is None:
        return
    if requested <= 0:
        return
    try:
        deadline = now + timedelta(seconds=requested)
    except OverflowError:
        deadline = datetime.max.replace(tzinfo=UTC)
    persist_deadline(db, now.isoformat(), deadline.isoformat())
