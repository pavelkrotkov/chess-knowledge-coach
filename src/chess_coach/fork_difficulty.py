"""Require two current matching fork successes before a harder search."""

import json
import sqlite3
import time

from .fork_difficulty_history import _pair
from .opening_queue_budget import BrowserBudget
from .tactical_course_budget import PreviewUnavailable


def by_attempt(db, subject, corpus, attempt):
    from .related_fork_assessment_scope import is_source

    row = db.connection.execute(
        "SELECT * FROM unified_sessions WHERE subject=? AND attempt_id=?", (subject, attempt)
    ).fetchone()
    if row is None or not is_source(row):
        raise ValueError("harder fork unavailable")
    evidence = json.loads(row["provenance_json"])["related_fork"]["evidence_id"]
    return eligible(db, subject, corpus, evidence, attempt)


def eligible(db, subject, corpus, evidence, attempt):
    try:
        budget = BrowserBudget(db)
        budget.expires = min(budget.expires, time.monotonic() + 3.0)
        with budget.scope(snapshot=False):
            return _pair(db, subject, corpus, evidence, attempt, budget.check)
    except (sqlite3.Error, TypeError, KeyError, IndexError, AttributeError, PreviewUnavailable):
        raise ValueError("harder fork unavailable") from None


def start_context(db, subject, corpus, evidence, prior):
    if prior is None or not prior.startswith("harder:"):
        return prior, None
    attempt = prior.removeprefix("harder:")
    if not attempt:
        raise ValueError("harder fork unavailable")
    return attempt, eligible(db, subject, corpus, evidence, attempt)
