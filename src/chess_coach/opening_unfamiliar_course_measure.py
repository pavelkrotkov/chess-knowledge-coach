"""Attach an optional exact current first-turn comparison without engine work."""

import time

from .opening_explore_recent import recent
from .opening_unfamiliar_course_hints import hints
from .opening_unfamiliar_course_proof import verify
from .opening_unfamiliar_measure_source import candidates, first_game
from .opening_unfamiliar_measure_state import checked
from .tactical_course_deadline import PreviewDeadline

COMPARISON_SECONDS = 8.0


def _lookup(db, root, learner, color, board, item, budget):
    with budget.scope(snapshot=False):
        games, _ = recent(db, learner)
    game_ids = hints(db, root, learner, board.fen(), item, budget)
    first = first_game(games, color)
    hinted = [(game, side) for game, side in games if game["id"] in game_ids]
    for found in candidates(db, learner, hinted, color, board.fen(), item, budget):
        value = checked(db, root, learner, *found, budget, identity=True)
        if value["status"] != "complete":
            continue
        result = verify(db, root, learner, found, value, budget)
        if result is None:
            continue
        decision = {key: found[0][key] for key in ("game_id", "position_id", "ply")}
        result["_decision"] = decision
        if decision["game_id"] != first:
            result["decision"] = decision
        return result
    return None


def current(db, root, learner, color, board, item, budget):
    original = budget.expires
    budget.expires = min(original - 1, time.monotonic() + COMPARISON_SECONDS)
    try:
        return _lookup(db, root, learner, color, board, item, budget)
    except (Exception, PreviewDeadline):
        return None
    finally:
        budget.expires = original
