"""Bounded legal recaptures on one square; not a complete tactical search."""

from .material_exchange_rules import ordinary_capture
from .material_exchange_tree import recaptures
from .material_values import VALUES as VALUES


def exchange(board, move):
    """Return material gain or None when this exchange is outside the boundary."""
    if not ordinary_capture(board, move):
        return None
    target = board.piece_at(move.to_square)
    if target is None or target.piece_type not in VALUES:
        return None
    mover = board.turn
    next_board = board.copy()
    next_board.push(move)
    return recaptures(next_board, move.to_square, mover, VALUES[target.piece_type], [0], 1)
