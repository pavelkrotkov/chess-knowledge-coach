"""Follow explicitly supplied branches without grading unlisted legal moves."""

import chess

from .puzzle_session_validate import legal_move
from .unified_session_branch import move_state


def apply_move(row, lines, candidates, submitted):
    board = chess.Board(row["current_fen"])
    try:
        move = legal_move(board, submitted)
    except ValueError:
        return move_state(board, "illegal", "active", row["next_index"], candidates)
    from .unified_session_legal_move import apply

    return apply(row, board, lines, candidates, move)
