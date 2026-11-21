"""Validate one replay move and classify its board's queen balance."""

from .opening_profile_center_moves import advance
from .style_history_lines import history_safe
from .style_transition_metrics import queens


def state(board):
    value = queens(board)
    if value["one_queen_each"]:
        return "one_each"
    return "preexisting_queenless" if value["queens"] == 0 else "start_imbalanced"


def step(board, row, ply):
    if not history_safe(board):
        return False
    move = board.parse_uci(row[2])
    if move.promotion:
        return False
    advance(board, [row], ply)
    return True
