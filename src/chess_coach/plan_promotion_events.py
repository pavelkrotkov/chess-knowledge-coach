"""Bound a promotion proof and all assistance across the attempt."""

import json

from .objective_events import MAX_EVENTS, assistance, prefix, response


def proof_events(db, session):
    request = db.connection.execute(
        """SELECT q.*,r.result_json FROM objective_requests q
        JOIN objective_results r ON r.attempt_id=q.attempt_id AND r.event_id=q.event_id
        WHERE q.attempt_id=? ORDER BY q.rowid DESC LIMIT 1""",
        (session["attempt_id"],),
    ).fetchone()
    if request is None:
        return None
    result = json.loads(request["result_json"])
    if result.get("status") != "correct" or result.get("assistance") != "unassisted":
        return None
    events = db.connection.execute(
        """SELECT event_id,kind,submitted_move,response_json,created_at
        FROM unified_session_events WHERE attempt_id=? ORDER BY rowid LIMIT ?""",
        (session["attempt_id"], MAX_EVENTS + 1),
    ).fetchall()
    if len(events) > MAX_EVENTS or assistance(events) != "unassisted":
        return None
    root = prefix(db, session["attempt_id"], request["event_id"])
    if assistance(root[:-1]) != result["assistance"]:
        return None
    return request, result, events[len(root) :]


def before_final(later, board):
    for event in later:
        if event["kind"] != "move" or response(event).get("feedback") != "illegal":
            return False
        if response(event).get("fen") != board.fen():
            return False
    return True
