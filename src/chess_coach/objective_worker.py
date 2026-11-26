"""Process a small subject-owned verification queue and qualified learning receipts."""

import time

from .learner_identity import normalize_identity
from .objective_fork_defense_reporting import work_limit
from .objective_pin_prevent_reporting import work_limit as pin_work_limit
from .objective_publication import publish
from .objective_verify import SECONDS, compute
from .objective_work_scope import require_capture_scope
from .objective_work_scope import scope as work_scope


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
    # A missing project must not create an irreversible unavailable result.
    require_capture_scope(db, rows[:limit], identity)
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
    result.update(pin_work_limit(rows[:limit]))
    return result


def _process_one(db, row, clock, seconds, verifier):
    with work_scope(row):
        result = verifier(db, row, clock, seconds=seconds)
        published = publish(db, row, result)
    from .unified_fork_worker import finish_objective

    finish_objective(db, row, published)
    return published
