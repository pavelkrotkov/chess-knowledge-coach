"""Read a private verification result without changing the original event."""

import json

from .learner_identity import normalize_identity
from .unified_session_state import session_row
from .unified_source_current import require_current


def latest(db, session):
    row = db.connection.execute(
        """SELECT q.event_id,r.result_json FROM objective_requests q LEFT JOIN objective_results r
        ON r.attempt_id=q.attempt_id AND r.event_id=q.event_id
        WHERE q.attempt_id=? AND q.subject=? ORDER BY q.rowid DESC LIMIT 1""",
        (session["attempt_id"], normalize_identity(session["subject"])),
    ).fetchone()
    return _view(row) if row else None


def inspect(db, subject, attempt, event):
    session = session_row(db, attempt, subject)
    row = db.connection.execute(
        """SELECT q.event_id,r.result_json FROM objective_requests q LEFT JOIN objective_results r
        ON r.attempt_id=q.attempt_id AND r.event_id=q.event_id
        WHERE q.attempt_id=? AND q.event_id=? AND q.subject=?""",
        (attempt, event, normalize_identity(subject)),
    ).fetchone()
    if row is None:
        raise ValueError("verification request unavailable")
    try:
        require_current(db, session)
    except (ValueError, TypeError, KeyError):
        return {"status": "unresolved", "reason": "source_unavailable"}
    return _view(row)


def _view(row):
    if row["result_json"] is None:
        return {"status": "pending"}
    result = json.loads(row["result_json"])
    return {key: result[key] for key in ("status", "reason", "assistance") if key in result}
