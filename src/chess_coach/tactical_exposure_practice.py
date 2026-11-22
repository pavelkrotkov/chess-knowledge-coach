"""Separate old unknown history from current Study delivery conflicts."""

import sqlite3
from datetime import UTC, datetime

from .learner_identity import normalize_identity
from .tactical_exposure_check import coverage
from .tactical_exposure_intents import check_intents
from .tactical_exposure_lookup import _times, practice_status


def _inspect(db, identity, key, now):
    try:
        if coverage(db) is None:
            return None
        return check_intents(db, identity, key, now), _times(db, identity, key)
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError):
        return None
    except sqlite3.Error as exc:
        if getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_INTERRUPT:
            raise
        return None


def check(db, subject, key):
    identity = normalize_identity(subject)
    if identity is None:
        return "unavailable"
    now = datetime.now(UTC)
    found = _inspect(db, identity, key, now)
    if found is None:
        return "unavailable"
    intent, times = found
    return practice_status(times, intent, now)
