"""Resume a snapshot-bound public promotion proof without changing its event."""

import json

from .objective_promotion_contract import OBJECTIVES
from .objective_promotion_resume import resume


def continuation(db, session):
    if session["source_type"] != "public" or session["objective"] not in OBJECTIVES:
        return None
    if session["status"] != "needs_verification":
        return None
    row = db.connection.execute(
        """SELECT q.*,r.result_json FROM objective_requests q JOIN objective_results r
        ON r.attempt_id=q.attempt_id AND r.event_id=q.event_id
        WHERE q.attempt_id=? ORDER BY q.rowid DESC LIMIT 1""",
        (session["attempt_id"],),
    ).fetchone()
    if row is None:
        return None
    result = json.loads(row["result_json"])
    if result.get("status") != "correct":
        return None
    return resume(db, session, row, result)


def append_reply(db, attempt, subject, steps):
    from .unified_session_state import session_row

    resumed = continuation(db, session_row(db, attempt, subject))
    if resumed and not resumed["complete"]:
        steps.append({"fen": resumed["board"].fen(), "label": "Reply: " + resumed["reply"]})
    return steps
