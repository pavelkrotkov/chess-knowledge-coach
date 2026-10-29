"""Resume a verified short-mate line from its immutable original proof."""

import json

from .objective_current import current
from .objective_history import before_answer
from .objective_short_source import VERSION
from .objective_short_witness import binding, resume


def continuation(db, session):
    if session["source_version"] != VERSION or session["status"] != "needs_verification":
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
    checked, events = current(db, row)
    board, move = before_answer(db, checked, events)
    binding(row, result, board)
    return resume(db, session, row, result, board, move)
