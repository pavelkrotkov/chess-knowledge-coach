"""Rebind a forced-promotion root to its immutable request and source."""

import json

from .objective_binding import matches
from .objective_current import _current
from .objective_events import assistance, response
from .objective_promotion_history import before_answer
from .objective_promotion_proof_binding import binding


def _scope(session, data, request):
    shadow = {**dict(session), "status": "needs_verification"}
    return session["status"] in {
        "needs_verification",
        "objective_verified",
        "line_completed",
    } and matches(shadow, data, request)


def root(db, row):
    requests = db.connection.execute(
        "SELECT * FROM objective_requests WHERE attempt_id=? ORDER BY rowid LIMIT 2",
        (row["attempt_id"],),
    ).fetchall()
    if len(requests) != 1:
        raise ValueError("forced promotion request unavailable")
    request = requests[0]
    session, events = _current(db, request, _scope)
    shadow = {**dict(session), "current_fen": response(events[-1])["fen"]}
    board, move = before_answer(db, shadow, events)
    raw = db.connection.execute(
        "SELECT result_json FROM objective_results WHERE attempt_id=? AND event_id=?",
        (row["attempt_id"], request["event_id"]),
    ).fetchone()
    if raw is None:
        raise ValueError("forced promotion result pending")
    result = json.loads(raw[0])
    binding(request, result, board, move)
    if assistance(events[:-1]) != result.get("assistance"):
        raise ValueError("forced promotion assistance changed")
    return request, result, board, move, events
