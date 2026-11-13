"""Attach an optional exact current first-turn comparison without engine work."""

from .opening_explore_recent import recent
from .opening_unfamiliar_course_proof import verify
from .opening_unfamiliar_measure_source import find
from .opening_unfamiliar_measure_state import checked
from .tactical_course_deadline import PreviewDeadline


def current(db, root, learner, color, board, item, budget):
    original = budget.expires
    budget.expires = original - 1
    try:
        with budget.scope(snapshot=False):
            games, _ = recent(db, learner)
        found = find(db, learner, games, color, board.fen(), item, budget)
        if not found:
            return None
        value = checked(db, root, learner, *found, budget, identity=True)
        if value["status"] != "complete":
            return None
        return verify(db, root, learner, found, value, budget)
    except (Exception, PreviewDeadline):
        return None
    finally:
        budget.expires = original
