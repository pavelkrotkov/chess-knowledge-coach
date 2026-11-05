"""Classify one played decision with bounded, history-aware mate proofs."""

from .pawn_scope import history_known
from .short_mate_game_immediate import immediate
from .short_mate_game_roots import solve


def classify(board, played, deadline, clock):
    if not board.is_valid():
        return "unknown", "invalid_position"
    if not history_known(board):
        return "unknown", "history_unavailable"
    moves = sorted(board.legal_moves, key=lambda item: item.uci())
    found = immediate(board, moves, deadline, clock)
    if found is None:
        return "unknown", "deadline"
    if found:
        return "immediate", None
    return solve(board, moves, played, deadline, clock)
