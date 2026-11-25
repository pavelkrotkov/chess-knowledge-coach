"""Verify early subject turns from one original standard-start game."""

from typing import cast

import chess

from .learner_context import decision_context_boards
from .opening_explore_guard import require_bounded
from .opening_storage import position_key
from .pipeline_inputs import game_input

TURNS = {"white": (1, 3), "black": (2,)}


def game(db, learner, game, color):
    require_bounded(db, game["id"])
    found = []
    for context, board in decision_context_boards(db, game["id"], learner=learner):
        ply = cast(int, context["ply"])
        if ply > 3:
            break
        if (board.root().fen(), context["learner_color"]) != (chess.Board().fen(), color):
            raise ValueError("opening history unavailable")
        if context["subject"] and ply in TURNS[color]:
            path = tuple(move.uci() for move in board.move_stack)
            found.append((position_key(board), path, context["played_move"]))
    if not found:
        raise ValueError("opening history unavailable")
    return found, game_input(db, game["id"])
