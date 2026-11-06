"""Validate one immutable capture request, event prefix, and result."""

import json

import chess

from .material_reply_guard import MAX_REPLIES
from .objective_capture_judge import VERSION as VERIFIER
from .objective_current import current
from .objective_events import assistance
from .objective_history_dispatch import replay as before_answer
from .objective_provenance import SECONDS
from .objective_short_history import history_hash


def _provenance(result, request):
    keys = (
        "objective_version",
        "history_mode",
        "snapshot_hash",
        "source_hash",
        "event_prefix_hash",
    )
    return (
        all(result.get(key) == request[key] for key in keys)
        and result.get("verifier") == VERIFIER
        and result.get("learning_eligible") is False
    )


def _move(result, board, move):
    return (
        result.get("history_hash") == history_hash(board)
        and result.get("move") == move.uci()
        and result.get("san") == board.san(move)
    )


# The worker records its bounded reply policy; old or malformed results
# are not interchangeable with the current verifier.
def _limits(result):
    limits = result.get("limits")
    if not isinstance(limits, dict):
        return False
    seconds = limits.get("compute_timeout_seconds")
    return (
        limits.get("plies") == 2
        and limits.get("reply_limit") == MAX_REPLIES
        and type(seconds) in {int, float}
        and 0 < seconds <= SECONDS
    )


# A proved or incorrect result must refer to the named target on this board.
def _outcome(result, board, move, target):
    captured = board.is_capture(move) and not board.is_en_passant(move) and move.to_square == target
    if result.get("status") == "correct":
        return (
            captured
            and result.get("reason") == "bounded_capture_proved"
            and result.get("proven_gain_floor") == 3
        )
    return (
        not captured
        and result.get("status") == "incorrect"
        and result.get("reason") == "named_target_not_captured"
    )


def _assistance(result, events, observed):
    help_used = assistance(events[:-1])
    if result.get("assistance") != help_used:
        return False
    if (observed["hints"] == 0) != (help_used == "unassisted"):
        return False
    return not observed["reveals"] or help_used == "revealed"


def _matches(result, request, events, board, move, target, observed):
    # Results must still match the immutable request and exact first-move prefix.
    if not _provenance(result, request):
        return False
    if result.get("status") == "unresolved":
        return True
    if not _assistance(result, events, observed):
        return False
    # Check only the recorded proof bounds, not a second proof on this page.
    return _limits(result) and _move(result, board, move) and _outcome(result, board, move, target)


def result(db, row, observed, *, related_cache=None):
    requests = db.connection.execute(
        "SELECT * FROM objective_requests WHERE attempt_id=? ORDER BY rowid LIMIT 2",
        (row["attempt_id"],),
    ).fetchall()
    if len(requests) != 1:
        return {"status": "unavailable"}
    request = requests[0]
    # Recheck the exact source and event prefix before trusting a worker result.
    session, events = current(db, request, related_cache=related_cache)
    board, move = before_answer(db, session, events, request)
    record = db.connection.execute(
        "SELECT result_json FROM objective_results WHERE attempt_id=? AND event_id=?",
        (row["attempt_id"], request["event_id"]),
    ).fetchone()
    if record is None:
        return {"status": "pending"}
    result = json.loads(record["result_json"])
    target = chess.parse_square(json.loads(row["provenance_json"])["objective_target"])
    if not _matches(result, request, events, board, move, target, observed):
        return {"status": "unavailable"}
    return {"status": result["status"], "assistance": result.get("assistance")}
