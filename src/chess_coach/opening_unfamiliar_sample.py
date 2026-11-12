"""Recheck first turns in the recent attributable game sample."""

import chess

from .learner_context import decision_context_boards
from .opening_explore_guard import require_bounded


def _first_turn(db, learner, game_id, color):
    require_bounded(db, game_id)
    contexts = decision_context_boards(db, game_id, learner=learner)
    first, board = next(contexts)
    if board.fen() != chess.Board().fen() or first["ply"] != 1:
        raise ValueError("nonstandard starting position")
    if color == "white":
        if not first["subject"]:
            raise ValueError("first turn unavailable")
        return first["played_move"]
    second, _after = next(contexts)
    if second["ply"] != 2 or not second["subject"]:
        raise ValueError("first reply unavailable")
    return first["played_move"], second["played_move"]


def sample(db, learner, games, budget):
    white, black, failed = [], [], 0
    for game, color in games:
        try:
            with budget.scope(snapshot=True):
                turn = _first_turn(db, learner, game["id"], color)
            (white if color == "white" else black).append(turn)
        except (ValueError, TypeError, StopIteration):
            failed += 1
    return white, black, failed
