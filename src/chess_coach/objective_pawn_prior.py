"""Recheck the earlier immutable pawn proof before replay."""

import json

from .learner_identity import normalize_identity
from .objective_binding import matches
from .objective_events import prefix, prefix_hash
from .objective_pawn_binding import binding


def proved(db, session, event, board):
    row = db.connection.execute(
        """SELECT q.*,r.result_json FROM objective_requests q JOIN objective_results r
        ON r.attempt_id=q.attempt_id AND r.event_id=q.event_id
        WHERE q.attempt_id=? AND q.event_id=?""",
        (session["attempt_id"], event["event_id"]),
    ).fetchone()
    if row is None:
        raise ValueError("pawn prior proof unavailable")
    result = json.loads(row["result_json"])
    if (
        result.get("status") != "correct"
        or result.get("continuation", {}).get("status") != "available"
    ):
        raise ValueError("pawn prior proof unavailable")
    _request_binding(db, session, row)
    binding(row, result, board, session)
    return result


def _request_binding(db, session, row):
    data = json.loads(session["provenance_json"])
    if normalize_identity(session["subject"]) != row["subject"] or not matches(session, data, row):
        raise ValueError("pawn prior request changed")
    events = prefix(db, row["attempt_id"], row["event_id"])
    if prefix_hash(events) != row["event_prefix_hash"]:
        raise ValueError("pawn prior history changed")
