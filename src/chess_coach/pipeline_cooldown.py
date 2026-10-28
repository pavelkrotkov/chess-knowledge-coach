"""Persist server-directed Lichess backoff before any retry wait."""

from datetime import datetime

from .db import Database
from .mastery_time import as_utc, parse_utc


def utc_now(clock) -> datetime:
    return as_utc(clock() if clock is not None else None)


def active_deadline(db: Database, clock) -> str | None:
    row = db.connection.execute("SELECT retry_until FROM pipeline_health WHERE id=1").fetchone()
    if row is None or row["retry_until"] is None:
        return None
    deadline = parse_utc(row["retry_until"])
    if deadline is None:
        raise ValueError("invalid persisted retry deadline")
    if deadline > utc_now(clock):
        return deadline.isoformat()
    return None


def stored_deadline(db: Database) -> str | None:
    row = db.connection.execute("SELECT retry_until FROM pipeline_health WHERE id=1").fetchone()
    return row["retry_until"] if row else None
