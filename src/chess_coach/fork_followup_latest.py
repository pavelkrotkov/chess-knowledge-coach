"""Find the latest current successful fork assessment."""

import time

from .fork_followup_prior import prior
from .objective_fork_contract import GOAL
from .opening_queue_budget import BrowserBudget


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
