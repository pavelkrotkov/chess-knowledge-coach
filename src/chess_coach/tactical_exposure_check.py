"""Check provided or uncertain tactical material at an answer boundary."""

import sqlite3
from datetime import UTC, datetime

from .learner_identity import normalize_identity
from .mastery_time import parse_utc
from .tactical_exposure_intents import check_intents
from .tactical_exposure_lookup import ledger_check


def coverage(db):
    version = db.connection.execute("PRAGMA user_version").fetchone()[0]
    if version < 38:
        return None
    row = db.connection.execute(
        "SELECT tracking_started_at FROM tactical_exposure_coverage WHERE id=1"
    ).fetchone()
    return parse_utc(row[0]) if row else None


def _check(db, subject, key, answered_at):
    identity = normalize_identity(subject)
    start = coverage(db)
    if not identity or start is None:
        return "coverage_unavailable"
    cutoff = datetime.now(UTC) if answered_at is None else parse_utc(answered_at)
    if cutoff is None:
        return "coverage_unavailable"
    try:
        intent = check_intents(db, identity, key, cutoff)
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError):
        return "coverage_unavailable"
    if intent == "provided":
        return intent
    return ledger_check(db, identity, key, cutoff, start, intent)


def check(db, subject, key, *, answered_at=None):
    try:
        return _check(db, subject, key, answered_at)
    except sqlite3.Error as exc:
        if getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_INTERRUPT:
            raise
        return "coverage_unavailable"
