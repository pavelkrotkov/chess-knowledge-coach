"""Process a small subject-owned queue without touching learning state."""

import time

from .learner_identity import normalize_identity
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
        result = verifier(db, row, clock, seconds=seconds)
        result = publish(db, row, result)
        outcomes[result["status"]] = outcomes.get(result["status"], 0) + 1
    capped = len(rows) > limit
    return {
        "status": "partial" if capped else "complete",
        "processed": min(len(rows), limit),
        "outcomes": outcomes,
        "limit": limit,
        "capped": capped,
    }
