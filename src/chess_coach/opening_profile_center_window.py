"""Validate a bounded ordered window against its exact parent positions."""

from .opening_profile_center_moves import advance, board_for

PLIES = 4


def _expected(first, total):
    if type(first) is not int or type(total) is not int or first < 1 or total < first:
        return None
    return min(PLIES, total - first + 1)


def validate(rows, first, total, parent, root):
    expected = _expected(first, total)
    if expected is None:
        return "unavailable", None
    if len(rows) != expected:
        return "inconsistent", None
    try:
        board = board_for(parent)
        original = board.copy()
        moves = advance(board, rows, first)
        if not moves or moves[0] != root:
            raise ValueError("ordered root differs")
        if expected < PLIES:
            return "short", None
        return "valid", (original, board, moves)
    except (ValueError, TypeError, IndexError, KeyError):
        return "inconsistent", None
