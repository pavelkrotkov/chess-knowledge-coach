"""Verify mate tasks against the immutable puzzle prompt."""

import chess

from .puzzle_session_validate import legal_move
from .tactical_rules import _mating_moves, mate_in_one_fact


def prompt_board(session) -> chess.Board:
    board = chess.Board(session["initial_fen"])
    board.push(legal_move(board, session["solution"].split()[0]))
    if board.fen() != session["current_fen"]:
        raise ValueError("puzzle prompt does not match the immutable snapshot")
    return board


def verified_mate(session, move: str) -> dict | None:
    return mate_in_one_fact(prompt_board(session).fen(), move)


def training_objective(session, item) -> str | None:
    if item["skill"] != "mate_in_one" or item["operation"] != "execute":
        return None
    if session["status"] != "active" or session["next_index"] != 1:
        return None
    return "Find mate in one." if _mating_moves(prompt_board(session)) else None
