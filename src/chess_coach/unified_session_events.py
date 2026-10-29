"""Apply and persist subject-owned practice moves and hints exactly once."""

from .objective_request import enqueue
from .objective_session_dispatch import record
from .objective_session_view import display
from .unified_session_replay import previous as _previous
from .unified_session_state import session_row
from .unified_source_current import require_current


def submit(db, attempt_id, subject, *, event_id, move):
    if not isinstance(move, str):
        raise ValueError("move must be UCI text")
    return _event(db, attempt_id, subject, event_id, "move", move)


def hint(db, attempt_id, subject, *, event_id):
    return _event(db, attempt_id, subject, event_id, "hint", None)


def reveal(db, attempt_id, subject, *, event_id):
    return _event(db, attempt_id, subject, event_id, "hint", "reveal")


def show(db, attempt_id, subject):
    row = session_row(db, attempt_id, subject)
    require_current(db, row)
    return display(db, row)


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
            else record(db, row, event_id, kind, move)
        )
        if previous is None:
            enqueue(db, row, event_id, result)
        db.connection.commit()
        return result
    except BaseException:
        db.connection.rollback()
        raise
