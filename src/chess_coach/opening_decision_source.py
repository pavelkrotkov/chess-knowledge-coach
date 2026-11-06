"""Reconstruct one attributable opening decision against current classification."""

from typing import cast

from .learner_context import decision_context_boards
from .opening_decision_budget import classification
from .opening_storage import position_key
from .recurrence_snapshot import read_snapshot


def _validate_board(board):
    if not board.is_valid() or board.outcome(claim_draw=False) is not None:
        raise ValueError("game history is unavailable")


def _history(db, game_id, position_id, learner, opening):
    target, last_match = None, 0
    for context, board in decision_context_boards(db, game_id, learner=learner):
        _validate_board(board)
        if context["position_id"] == position_id and context["subject"]:
            target = context, board
        after = board.copy()
        after.push_uci(cast(str, context["played_move"]))
        if position_key(after) == opening["position_key"]:
            last_match = cast(int, context["ply"])
    if target is None or cast(int, target[0]["ply"]) > last_match:
        raise ValueError("owned opening decision unavailable")
    return target


def source(db, game_id, position_id, learner):
    with read_snapshot(db):
        opening = classification(db, game_id)
    context, board = _history(db, game_id, position_id, learner, opening)
    return opening, context, board
