"""Verify bounded capture objectives without inferring a game result."""

import chess

from .material_reply_guard import MAX_REPLIES
from .objective_capture_proof import capture, unknown
from .objective_capture_scope import reason as scope_reason
from .objective_judge import _scope_reason
from .objective_short_history import history_hash

VERSION = "capture-objective-verifier-v1"


def judge(board, move, objective, target, threshold, clock, start, seconds, base):
    reason = scope_reason(board, move, clock, start, seconds)
    if reason:
        return unknown(base, reason)
    result = {
        **base,
        "verifier": VERSION,
        "history_hash": history_hash(board),
        "move": move.uci(),
        "san": board.san(move),
        "limits": {"plies": 2, "reply_limit": MAX_REPLIES, "compute_timeout_seconds": seconds},
    }
    return capture(board, move, objective, target, threshold, clock, start, seconds, result)


def verify(board, move, request, events, clock, start, seconds, base, data):
    reason = _scope_reason(board, request, events)
    if reason:
        return unknown(base, reason)
    try:
        target = chess.parse_square(data["objective_target"])
        threshold = data["gain_threshold"]
        objective = data["capture_objective"]
        if (
            type(threshold) is not int
            or threshold != 3
            or objective not in {"capture_named_target", "bounded_material_gain"}
        ):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        return unknown(base, "objective_binding_unavailable")
    return judge(board, move, objective, target, threshold, clock, start, seconds, base)
