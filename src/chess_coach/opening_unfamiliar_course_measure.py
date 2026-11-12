"""Attach an optional exact current first-turn comparison without engine work."""

import time

from .opening_explore_recent import recent
from .opening_unfamiliar_course_proof import verify
from .opening_unfamiliar_measure_source import candidates
from .opening_unfamiliar_measure_state import checked
from .tactical_course_deadline import PreviewDeadline

COMPARISON_SECONDS = 8.0


def current(db, root, learner, color, board, item, budget):
    original = budget.expires
    budget.expires = min(original - 1, time.monotonic() + COMPARISON_SECONDS)
    try:
        with budget.scope(snapshot=False):
            games, _ = recent(db, learner)
        for index, found in enumerate(
            candidates(db, learner, games, color, board.fen(), item, budget)
        ):
            value = checked(db, root, learner, *found, budget, identity=True)
            if value["status"] != "complete":
                continue
            result = verify(db, root, learner, found, value, budget)
            if result and index:
                decision = found[0]
                result["decision"] = {
                    key: decision[key] for key in ("game_id", "position_id", "ply")
                }
            return result
        return None
    except (Exception, PreviewDeadline):
        return None
    finally:
        budget.expires = original
