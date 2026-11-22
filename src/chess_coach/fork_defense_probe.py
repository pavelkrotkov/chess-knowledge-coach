"""Identify positional fork candidates without inventing game history."""

from .fork_defense_candidates import positional_candidates
from .fork_defense_history import unsupported

MAX_MOVES = 128
MAX_CANDIDATES = 16


def hypothetical(board, *, check=None):
    tick = check or (lambda: None)
    if unsupported(board):
        return None
    probe = board.copy(stack=False)
    probe.turn = not probe.turn
    if not probe.is_valid() or probe.is_check():
        return None
    moves = list(probe.legal_moves)
    if len(moves) > MAX_MOVES:
        return None
    result = positional_candidates(probe, moves, tick)
    return result if len(result) <= MAX_CANDIDATES else None
