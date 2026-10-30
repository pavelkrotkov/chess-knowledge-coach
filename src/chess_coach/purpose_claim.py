"""Atomically claim or recover one explicit purpose request."""

from .purpose_attempts import record
from .purpose_config import MAX_ATTEMPTS
from .purpose_current import current, owned


def claim(db, request_id, learner, *, retry):
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        row = owned(db, request_id, learner)
        if row["status"] == "running":
            record(db, row, "interrupted", "worker_interrupted", {})
            db.connection.commit()
            return None, "interrupted"
        if row["status"] == "complete":
            state = completed_state(db, row, learner)
            db.connection.commit()
            return None, state
        if row["attempt_count"] >= MAX_ATTEMPTS or (row["attempt_count"] and not retry):
            db.connection.commit()
            return None, "retry_required_or_exhausted"
        try:
            snapshot, config = current(db, row, learner)
        except ValueError:
            row = started(db, request_id, learner)
            record(db, row, "stale", "source_changed", {})
            db.connection.commit()
            return None, "stale"
        row = started(db, request_id, learner)
        db.connection.commit()
        return (row, snapshot, config), None
    except BaseException:
        db.connection.rollback()
        raise


def started(db, request_id, learner):
    db.connection.execute(
        "UPDATE purpose_analysis_requests SET status=?,attempt_count=attempt_count+1 WHERE id=?",
        ("running", request_id),
    )
    return owned(db, request_id, learner)


def completed_state(db, row, learner):
    try:
        current(db, row, learner)
    except ValueError:
        return "stale"
    return "complete"
