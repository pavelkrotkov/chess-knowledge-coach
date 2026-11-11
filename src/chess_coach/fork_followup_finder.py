"""Find the next comparable fork only on an explicit learner request."""

import time

from .fork_followup_prior import prior
from .objective_fork_contract import GOAL
from .opening_queue_budget import BrowserBudget
from .recurrence_cursor import MAX_ID
from .recurrence_sources import evidence
from .related_fork_assessment_finder import SECONDS, find


def followup(db, subject, corpus, secret, attempt):
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    evidence_id, expected = prior(db, subject, corpus, attempt)
    found = find(db, subject, evidence_id, corpus, secret, expected=expected)
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
        raise ValueError("fork comparison changed")
    return evidence_id, found


def latest(db, subject, corpus):
    started = time.monotonic()
    with BrowserBudget(db).scope(snapshot=False):
        attempts = db.connection.execute(
            """SELECT attempt_id FROM unified_sessions INDEXED BY idx_unified_sessions_subject
            WHERE subject=? AND source_type=? AND objective=?
            ORDER BY started_at DESC,attempt_id LIMIT 20""",
            (subject, "corpus", GOAL),
        ).fetchall()
    for row in attempts:
        if time.monotonic() - started >= 3:
            break
        try:
            prior(db, subject, corpus, row["attempt_id"])
            return row["attempt_id"]
        except (ValueError, TypeError, KeyError, IndexError):
            continue
    return None


def first(db, subject, corpus, secret):
    started = time.monotonic()
    with BrowserBudget(db).scope(snapshot=False):
        sources, _ = evidence(db, subject, "fork", "execute", MAX_ID, failure_only=True, limit=20)
    for source in sources[:3]:
        if time.monotonic() - started >= SECONDS:
            break
        try:
            result = find(db, subject, source["id"], corpus, secret, started=started)
            if result:
                return source["id"], result
        except (ValueError, TypeError, KeyError, IndexError):
            continue
    return None, None
