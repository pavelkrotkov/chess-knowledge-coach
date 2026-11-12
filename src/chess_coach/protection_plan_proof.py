"""Validate a stored protection verdict without rerunning the proof."""

import chess

from .capture_plan_result import _move
from .material_reply_guard import MAX_REPLIES
from .objective_events import assistance
from .objective_protection_judge import VERSION
from .objective_provenance import SECONDS


# The immutable request binds the recorded proof to the current source and event prefix.
def valid(result, request, events, board, move, data):
    keys = (
        "objective_version",
        "history_mode",
        "snapshot_hash",
        "source_hash",
        "event_prefix_hash",
    )
    if not all(result.get(key) == request[key] for key in keys):
        return False
    if (result.get("verifier"), result.get("learning_eligible"), result.get("assistance")) != (
        VERSION,
        False,
        "unassisted",
    ) or assistance(events[:-1]) != "unassisted":
        return False
    if not _limits(result) or not _move(result, board, move):
        return False
    return _outcome(result, board, move, data)


def _limits(result):
    limits = result.get("limits", {})
    seconds = limits.get("compute_timeout_seconds")
    return (
        limits.get("plies") == 3
        and limits.get("reply_limit") == MAX_REPLIES
        and type(seconds) in {int, float}
        and 0 < seconds <= SECONDS
    )


# A negative verdict must retain a legal capture of the same physical target.
def _outcome(result, board, move, data):
    original = chess.parse_square(data["objective_target"])
    target = move.to_square if move.from_square == original else original
    after = board.copy()
    after.push(move)
    if result.get("legal_replies") != sorted(reply.uci() for reply in after.legal_moves):
        return False
    if result.get("status") == "correct":
        return result.get("reason") == "no_profitable_immediate_capture"
    if (result.get("status"), result.get("reason")) != ("incorrect", "profitable_capture"):
        return False
    reply = after.parse_uci(result["capture_reply"])
    return after.is_capture(reply) and reply.to_square == target
