"""Recheck the exact owned parent and pinned catalog alternative."""

from .opening_decision import inspect
from .opening_measure_source import selection
from .opening_unfamiliar_measure_first import first_turn


def _choice(decision, suggestion):
    return next(
        (
            item
            for item in decision["catalog"]["items"]
            if item["uci"] == suggestion["uci"] and item["child"] == suggestion["child_key"]
        ),
        None,
    )


def candidate(db, learner, game_id, color, parent, suggestion):
    first = first_turn(db, learner, game_id, color)
    if first is None or first[1].fen() != parent:
        return None
    decision = inspect(db, game_id, first[0]["position_id"], learner, alternative=suggestion["uci"])
    if decision["color"] != color or decision["fen"] != parent:
        return None
    choice = _choice(decision, suggestion)
    if choice is None:
        return None
    selection(db, game_id, first[0]["position_id"], learner, choice["uci"])
    return decision, choice
