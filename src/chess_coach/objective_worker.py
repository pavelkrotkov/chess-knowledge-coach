"""Process a small subject-owned queue without touching learning state."""

import time

from .learner_identity import normalize_identity
from .objective_fork_defense_budget import scope as fork_budget_scope
from .objective_fork_defense_reporting import work_limit
from .objective_publication import publish
from .objective_verify import SECONDS, compute


def process(db, subject, *, limit=4, clock=time.monotonic, seconds=SECONDS, verifier=compute):
    identity = normalize_identity(subject)
    if not identity or type(limit) is not int or not 1 <= limit <= 20 or not 0 < seconds <= SECONDS:
        raise ValueError("invalid verification worker limits")
    if db.connection.in_transaction:
        raise RuntimeError("verification worker requires an idle database")
    rows = db.connection.execute(
        """SELECT q.* FROM objective_requests q LEFT JOIN objective_results r
        ON r.attempt_id=q.attempt_id AND r.event_id=q.event_id
        WHERE q.subject=? AND r.attempt_id IS NULL ORDER BY q.rowid LIMIT ?""",
        (identity, limit + 1),
    ).fetchall()
    outcomes = {}
    for row in rows[:limit]:
        result = _process_one(db, row, clock, seconds, verifier)
        outcomes[result["status"]] = outcomes.get(result["status"], 0) + 1
    capped = len(rows) > limit
    result = {
        "status": "partial" if capped else "complete",
        "processed": min(len(rows), limit),
        "outcomes": outcomes,
        "limit": limit,
        "capped": capped,
    }
    result.update(work_limit(rows[:limit]))
    return result


def _process_one(db, row, clock, seconds, verifier):
    with fork_budget_scope():
        result = verifier(db, row, clock, seconds=seconds)
        return publish(db, row, result)
