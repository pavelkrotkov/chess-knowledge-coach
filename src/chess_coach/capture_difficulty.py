"""Bounded eligibility and identity for the optional harder capture search."""

import sqlite3
import time

from .capture_difficulty_context import context
from .capture_difficulty_history import pair
from .tactical_course_budget import SLICE_SECONDS, Budget, PreviewUnavailable

SECONDS = 3.0


def checked(db, subject, corpus, position, attempt, check):
    """Use the caller's existing deadline for the real eligibility checks."""
    if not isinstance(attempt, str) or not attempt or len(attempt) > 128 or not attempt.isascii():
        raise ValueError("harder capture unavailable")
    check()
    recent, earlier = pair(db, subject, corpus, position, attempt, check)
    expected, band, side = context(db, corpus, recent, earlier, check)
    check()
    return {
        "position": position,
        "earlier": earlier["attempt_id"],
        "attempt": attempt,
        "expected": expected,
        "band": band,
        "side": side,
    }


def operation_check(db):
    try:
        budget = Budget(db)
    except (sqlite3.Error, PreviewUnavailable):
        raise ValueError("harder capture unavailable") from None
    budget.expires = min(budget.expires, time.monotonic() + min(SECONDS, SLICE_SECONDS))

    def check():
        try:
            budget.check()
        except (sqlite3.Error, PreviewUnavailable):
            raise ValueError("harder capture unavailable") from None

    return check


def eligible(db, subject, corpus, position, attempt, check=None):
    try:
        return checked(db, subject, corpus, position, attempt, check or operation_check(db))
    except (sqlite3.Error, TypeError, KeyError, IndexError, AttributeError, PreviewUnavailable):
        raise ValueError("harder capture unavailable") from None
