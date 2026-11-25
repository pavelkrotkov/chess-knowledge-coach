"""Replay an owned standard first turn within bounded source limits."""

from typing import cast

import chess

from .learner_context import decision_context_boards
from .opening_explore_guard import require_bounded


def first_turn(db, learner, game_id, color):
    require_bounded(db, game_id)
    turns = decision_context_boards(db, game_id, learner=learner)
    first, board = next(turns)
    if first["ply"] != 1 or board.fen() != chess.Board().fen():
        return None
    context = first
    if color == "black":
        context, board = next(turns)
    expected = 1 if color == "white" else 2
    if context["ply"] != expected or not context["subject"]:
        return None
    return context, board


def at_path(db, learner, game_id, color, path):
    require_bounded(db, game_id)
    for context, board in decision_context_boards(db, game_id, learner=learner):
        if cast(int, context["ply"]) > len(path) + 1:
            break
        if (
            context["subject"]
            and context["learner_color"] == color
            and board.root().fen() == chess.Board().fen()
            and tuple(move.uci() for move in board.move_stack) == tuple(path)
        ):
            return context, board
    return None
