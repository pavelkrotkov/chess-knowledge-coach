"""Bind an optional reused board to verified report-snapshot history."""

from .decision_history import decision_board
from .mate_inspection_source import position_row


def board_for(db, view, board, history):
    if board is None:
        return decision_board(db, position_row(db, view["position_id"]))
    if history is None or history.db is not db:
        raise ValueError("verified history unavailable")
    fresh = history.board(view["game_id"], view["position_id"])
    if fresh.fen() != board.fen() or fresh.move_stack != board.move_stack:
        raise ValueError("verified history changed")
    return board
