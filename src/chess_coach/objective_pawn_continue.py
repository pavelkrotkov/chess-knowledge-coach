"""Resume an immutable pawn result with its separately proved training reply."""

import json

from .objective_pawn_contract import is_source
from .objective_pawn_resume import resume


def continuation(db, session):
    if not is_source(session) or session["status"] != "needs_verification":
        return None
    row = db.connection.execute(
        """SELECT q.*,r.result_json FROM objective_requests q LEFT JOIN objective_results r
        ON r.attempt_id=q.attempt_id AND r.event_id=q.event_id
        WHERE q.attempt_id=? ORDER BY q.rowid DESC LIMIT 1""",
        (session["attempt_id"],),
    ).fetchone()
    if row is None or row["result_json"] is None:
        return None
    result = json.loads(row["result_json"])
    if (
        result.get("status") != "correct"
        or result.get("continuation", {}).get("status") != "available"
    ):
        return None
    return resume(db, session, row, result)


def append_reply(db, attempt, subject, steps):
    from .unified_session_state import session_row

    resumed = continuation(db, session_row(db, attempt, subject))
    if resumed:
        steps.append(
            {"fen": resumed["board"].fen(), "label": "Training reply: " + resumed["reply"]}
        )
    return steps
