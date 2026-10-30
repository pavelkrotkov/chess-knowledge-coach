"""Verify a quiet defense against all supported immediate fork replies."""

from .objective_capture_proof import unknown
from .objective_fork_defense_assess import assess
from .objective_fork_defense_scope import supported_root
from .objective_judge import _scope_reason


def verify(board, move, request, events, clock, start, seconds, base, data):
    reason = _scope_reason(board, request, events)
    if reason:
        return unknown(base, reason)
    if data.get("threat_origin") != "positional_before_played":
        return unknown(base, "objective_binding_unavailable")
    if not supported_root(board):
        return unknown(base, "history_or_root_unresolved")
    if clock() - start > seconds or not move or move not in board.legal_moves:
        return unknown(base, "timeout_or_move_unavailable")
    return assess(board, move, clock, start, seconds, base)
