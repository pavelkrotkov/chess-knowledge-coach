"""Replay and verify a qualified mate decision from its prompt."""

import chess

from .puzzle_session_validate import legal_move
from .tactical_rules import mate_in_one_fact


def proof(row, event):
    board = chess.Board(row["prompt_fen"])
    move = legal_move(board, event["submitted_move"])
    fact = mate_in_one_fact(board.fen(), move.uci())
    board.push(move)
    if fact is None or board.fen() != row["current_fen"]:
        raise ValueError("terminal move is unavailable")
    expected = "objective_verified" if board.is_checkmate() else "line_completed"
    if row["status"] != expected or fact["played_checkmate"] != board.is_checkmate():
        raise ValueError("terminal outcome does not match")
    return fact
