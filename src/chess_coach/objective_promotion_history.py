"""Replay a standalone public position and its immutable pre-answer events."""

import chess

from .objective_answer import answer
from .objective_history_replay import replay
from .pawn_scope import history_known


def before_answer(db, session, events):
    board = chess.Board(session["prompt_fen"])
    if not board.is_valid() or not history_known(board):
        raise ValueError("public promotion history unavailable")
    for event in events[:-1]:
        replay(board, event)
    return board, answer(board, session, events[-1])
