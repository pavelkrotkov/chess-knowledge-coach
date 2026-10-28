"""Validate completion lineage and the recorded terminal chess decision."""

import chess

from .mastery_position import position_key
from .puzzle_session_validate import legal_move, validate_line
from .tactical_rules import mate_in_one_fact


def verified_prompt(row, outcome: str) -> str:
    prompt_fen = validate_line(row["initial_fen"], row["solution"])
    board = chess.Board(prompt_fen)
    move = legal_move(board, row["submitted_move"])
    fact = mate_in_one_fact(board.fen(), move.uci())
    if fact is None or fact["played_checkmate"] != (outcome == "success"):
        raise ValueError("completion does not match verified outcome")
    board.push(move)
    if board.fen() != row["current_fen"]:
        raise ValueError("completion board does not match move")
    return position_key(chess.Board(prompt_fen))
