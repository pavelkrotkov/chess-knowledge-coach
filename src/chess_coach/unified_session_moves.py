"""Follow explicitly supplied branches without grading unlisted legal moves."""

import chess

from .objective_pawn_contract import is_source as pawn_source
from .puzzle_session_validate import legal_move
from .unified_session_branch import advance, move_state


def apply_move(row, lines, candidates, submitted):
    board = chess.Board(row["current_fen"])
    try:
        move = legal_move(board, submitted)
    except ValueError:
        return move_state(board, "illegal", "active", row["next_index"], candidates)
    board.push(move)
    index = row["next_index"]
    if pawn_source(row):
        return move_state(board, "needs_verification", "needs_verification", index, candidates)
    matched = [i for i in candidates if index < len(lines[i]) and lines[i][index] == move.uci()]
    if not matched:
        return move_state(board, "needs_verification", "needs_verification", index, candidates)
    return advance(board, row["objective"], lines, matched, index)
