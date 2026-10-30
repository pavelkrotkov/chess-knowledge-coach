"""Prove only equivalent named pins within the qualified bounded kernel."""

from .objective_capture_proof import unknown
from .objective_judge import _scope_reason
from .objective_pin_binding import binding
from .objective_pin_proof import matching
from .objective_short_history import history_hash
from .pin_proof import MAX_REPLIES


def verify(board, move, request, events, clock, start, seconds, base, data):
    reason = _scope_reason(board, request, events)
    if reason:
        return unknown(base, reason)
    try:
        named = binding(board, data)
    except (ValueError, KeyError, TypeError):
        return unknown(base, "objective_binding_unavailable")
    return _judge(board, move, *named, clock, start, seconds, base)


def _judge(board, move, origin, pinned, rear, kind, clock, start, seconds, base):
    if clock() - start > seconds:
        return unknown(base, "timeout")
    if not move or move not in board.legal_moves or move.from_square != origin:
        return unknown(base, "named_attacker_or_move_unavailable")
    proof = matching(board, move, pinned, rear, kind)
    if clock() - start > seconds:
        return unknown(base, "timeout")
    if not proof:
        return unknown(base, "pin_or_consequence_unresolved")
    return {
        **base,
        "status": "correct",
        "reason": "named_pin_and_bounded_consequence_proved",
        "history_hash": history_hash(board),
        "move": move.uci(),
        "san": board.san(move),
        "proof": proof,
        "limits": {"reply_limit": MAX_REPLIES, "compute_timeout_seconds": seconds},
    }
