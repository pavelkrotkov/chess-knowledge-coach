"""Record answers and assistance exactly once, separate from move execution."""

import json

from .probe_event_storage import record
from .probe_validation import validate
from .probe_views import checked_row


def event(db, subject, attempt_id, event_id, kind, answer=None):
    validate(event_id, kind, answer)
    if db.connection.in_transaction:
        raise RuntimeError("cannot submit during a transaction")
    request = json.dumps({"kind": kind, "answer": answer}, sort_keys=True)
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        row, task = checked_row(db, subject, attempt_id)
        previous = db.connection.execute(
            "SELECT request_json,response_json FROM diagnostic_probe_events WHERE attempt_id=? AND event_id=?",
            (attempt_id, event_id),
        ).fetchone()
        if previous:
            if previous["request_json"] != request:
                raise ValueError("event ID belongs to another request")
            response = json.loads(previous["response_json"])
        else:
            response = record(db, row, task, event_id, kind, answer, request)
        db.connection.commit()
        return response
    except BaseException:
        db.connection.rollback()
        raise
