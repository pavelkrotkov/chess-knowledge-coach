"""Revalidate a complete, source-bound immediate-promotion assessment."""

import json

from .mate_assessment_events import replay as replay_all
from .objective_current import current
from .objective_history_dispatch import replay as replay_answer
from .objective_promotion_proof_binding import attempt, immediate
from .training_feedback_request import validate_request
from .unified_training_canonical_promotion import SOURCE as SOURCE
from .unified_training_canonical_promotion import binding

SKILL = "promotion"
POLICY = "unified-canonical-promote-now-schedule-v1"
MAPPER = "unified-canonical-promote-now-evidence-v1"


def proof(db, row, event_id=None):
    item = binding(db, row)
    if item is None:
        raise ValueError("canonical promotion enrollment unavailable")
    request = db.connection.execute(
        "SELECT * FROM objective_requests WHERE attempt_id=? ORDER BY rowid LIMIT 2",
        (row["attempt_id"],),
    ).fetchall()
    if len(request) != 1 or (event_id is not None and request[0]["event_id"] != event_id):
        raise ValueError("canonical promotion answer unavailable")
    session, events = current(db, request[0])
    board, move = replay_answer(db, session, events, request[0])
    recorded = db.connection.execute(
        "SELECT result_json FROM objective_results WHERE attempt_id=? AND event_id=?",
        (row["attempt_id"], request[0]["event_id"]),
    ).fetchone()
    if recorded is None:
        raise ValueError("canonical promotion result pending")
    result = json.loads(recorded[0])
    status = immediate(request[0], result, board, move)
    observed = replay_all(db, session)
    attempt(events, result, observed, row["hints_used"])
    event = events[-1]
    fact = {
        "status": status,
        "reason": result["reason"],
        "verifier": result["verifier"],
        "history_hash": result["history_hash"],
        "event_prefix_hash": result["event_prefix_hash"],
        "move": move.uci(),
        "promotion": bool(move.promotion),
    }
    _, fingerprint = validate_request(
        row["attempt_id"],
        event["event_id"],
        event["submitted_move"],
        item["item_id"],
        row["subject"],
    )
    return item, event, fact, bool(observed["hints"]), fingerprint
