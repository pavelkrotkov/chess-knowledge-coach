"""Find the next comparable fork only on an explicit learner request."""

import time

from .fork_difficulty_selection import signed_attempt
from .fork_followup_latest import latest as latest
from .fork_followup_prior import prior
from .fork_followup_reference import seal_result
from .opening_queue_budget import BrowserBudget
from .recurrence_cursor import MAX_ID
from .recurrence_sources import evidence
from .related_fork_assessment_finder import SECONDS, find


def followup(db, subject, corpus, secret, attempt, *, difficulty=None):
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    evidence_id, expected = (
        prior(db, subject, corpus, attempt)
        if difficulty is None
        else (difficulty["evidence"], difficulty["expected"])
    )
    options = {"difficulty": difficulty} if difficulty else {}
    found = find(db, subject, evidence_id, corpus, secret, expected=expected, **options)
    found = seal_result(secret, found, signed_attempt(attempt, difficulty), expected)
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
        raise ValueError("fork comparison changed")
    return evidence_id, found


def first(db, subject, corpus, secret):
    started = time.monotonic()
    with BrowserBudget(db).scope(snapshot=False):
        sources, _ = evidence(db, subject, "fork", "execute", MAX_ID, failure_only=True, limit=20)
    for source in sources:
        if time.monotonic() - started >= SECONDS:
            break
        try:
            result = find(db, subject, source["id"], corpus, secret, started=started)
            if result:
                return source["id"], result
        except (ValueError, TypeError, KeyError, IndexError):
            continue
    return None, None
