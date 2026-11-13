"""Bounded current evidence for an optional harder protection assessment."""

import sqlite3
import time

from .fact_fingerprint import canonical, digest
from .opening_queue_budget import BrowserBudget
from .protection_difficulty_history import _band, _pair
from .tactical_course_budget import PreviewUnavailable


def scope(base, evidence, attempt):
    return digest(canonical([base, "protection-harder-v1", evidence, attempt]))


def eligible(db, subject, corpus, evidence, attempt):
    try:
        budget = BrowserBudget(db)
        budget.expires = min(budget.expires, time.monotonic() + 3.0)
        with budget.scope(snapshot=False):
            recent, earlier = _pair(db, subject, corpus, evidence, attempt, budget.check)
            return _band(db, corpus, recent, earlier, budget.check)
    except (sqlite3.Error, TypeError, KeyError, IndexError, AttributeError, PreviewUnavailable):
        raise ValueError("harder protection unavailable") from None


def decorate(db, subject, corpus, result):
    if result.get("status") == "correct":
        try:
            eligible(db, subject, corpus, result["evidence_id"], result["attempt"])
            result["harder"] = True
        except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError, PreviewUnavailable):
            pass
    return result
