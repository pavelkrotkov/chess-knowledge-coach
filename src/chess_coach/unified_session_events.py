"""Apply and persist subject-owned practice moves and hints exactly once."""

import json

from .unified_session_apply import record_event
from .unified_session_state import session_row, view
from .unified_source_current import require_current


def submit(db, attempt_id, subject, *, event_id, move):
    if not isinstance(move, str):
        raise ValueError("move must be UCI text")
    return _event(db, attempt_id, subject, event_id, "move", move)


def hint(db, attempt_id, subject, *, event_id):
    return _event(db, attempt_id, subject, event_id, "hint", None)


def show(db, attempt_id, subject):
    row = session_row(db, attempt_id, subject)
    require_current(db, row)
    return view(row)


def _event(db, attempt_id, subject, event_id, kind, move):
    if not isinstance(event_id, str) or not event_id or len(event_id) > 256:
        raise ValueError("event ID is required")
    if db.connection.in_transaction:
        raise RuntimeError("cannot submit during an existing transaction")
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        row = session_row(db, attempt_id, subject)
        require_current(db, row)
        previous = db.connection.execute(
            """SELECT kind,submitted_move,response_json FROM unified_session_events
            WHERE attempt_id=? AND event_id=?""",
            (attempt_id, event_id),
        ).fetchone()
        result = (
            _previous(previous, kind, move, row["source_type"])
            if previous
            else record_event(db, row, event_id, kind, move)
        )
        db.connection.commit()
        return result
    except BaseException:
        db.connection.rollback()
        raise


def _previous(previous, kind, move, source_type):
    if (previous["kind"], previous["submitted_move"]) != (kind, move):
        raise ValueError("event ID belongs to another request")
    result = json.loads(previous["response_json"])
    if source_type == "own-game":
        result.pop("source_key", None)
        result.pop("objective_target", None)
    return result
