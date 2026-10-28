"""Verify a mate against the immutable puzzle prompt."""

import chess

from .puzzle_session_validate import legal_move
from .tactical_rules import mate_in_one_fact


def verified_mate(session, move: str) -> dict | None:
    board = chess.Board(session["initial_fen"])
    board.push(legal_move(board, session["solution"].split()[0]))
    if board.fen() != session["current_fen"]:
        raise ValueError("puzzle prompt does not match the immutable snapshot")
    fact = mate_in_one_fact(board.fen(), move)
    return fact if fact is not None and fact["played_checkmate"] else None
