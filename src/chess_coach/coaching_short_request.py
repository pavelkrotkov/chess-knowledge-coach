"""Recheck one immutable owned short-mate request and its proved move."""

import json

from .objective_current import short_terminal
from .objective_events import response
from .objective_history import recorded_before_answer
from .objective_short_witness import binding, continuation


def verified(db, row, event):
    request = db.connection.execute(
        """SELECT q.*,r.result_json FROM objective_requests q JOIN objective_results r
        ON r.attempt_id=q.attempt_id AND r.event_id=q.event_id
        WHERE q.attempt_id=? AND q.event_id=?""",
        (row["attempt_id"], event["event_id"]),
    ).fetchone()
    if request is None:
        return None
    result = json.loads(request["result_json"])
    if (
        not isinstance(result, dict)
        or result.get("status") != "correct"
        or result.get("assistance") != "unassisted"
    ):
        return None
    session, prefix = short_terminal(db, request)
    board, move = recorded_before_answer(db, session, prefix)
    binding(request, result, board)
    played = board.copy(stack=True)
    played.push(move)
    if response(event).get("fen") != played.fen():
        raise ValueError("verification move changed")
    return continuation(result, board, move)
