"""Bounded eligibility and identity for the optional harder capture search."""

import sqlite3
import time

from .capture_difficulty_context import context
from .capture_difficulty_history import pair
from .opening_queue_budget import BrowserBudget
from .tactical_course_budget import PreviewUnavailable

SECONDS = 3.0


def eligible(db, subject, corpus, position, attempt, check=lambda: None):
    if not isinstance(attempt, str) or not attempt or len(attempt) > 128 or not attempt.isascii():
        raise ValueError("harder capture unavailable")
    try:
        budget = BrowserBudget(db)
        budget.expires = min(budget.expires, time.monotonic() + SECONDS)
        with budget.scope(snapshot=False):

            def bounded():
                budget.check()
                check()

            recent, earlier = pair(db, subject, corpus, position, attempt, bounded)
            expected, band, side = context(db, corpus, recent, earlier, bounded)
            return {
                "position": position,
                "earlier": earlier["attempt_id"],
                "attempt": attempt,
                "expected": expected,
                "band": band,
                "side": side,
            }
    except (sqlite3.Error, TypeError, KeyError, IndexError, AttributeError, PreviewUnavailable):
        raise ValueError("harder capture unavailable") from None
