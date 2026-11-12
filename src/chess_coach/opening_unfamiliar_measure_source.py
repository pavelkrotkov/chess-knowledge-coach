"""Find a verified owned decision at an experiment's exact first-turn parent."""

import time

from .opening_unfamiliar_measure_decision import candidate
from .tactical_course_deadline import PreviewDeadline


def candidates(db, learner, games, color, parent, suggestion, budget):
    for game, side in games:
        if side != color:
            continue
        try:
            with budget.scope(snapshot=False):
                found = candidate(db, learner, game["id"], color, parent, suggestion)
            if found:
                yield found
        except (ValueError, TypeError, IndexError, StopIteration):
            continue


def find(db, learner, games, color, parent, suggestion, budget):
    return next(candidates(db, learner, games, color, parent, suggestion, budget), None)


def earlier(db, learner, games, color, board, item, budget, decision):
    original = budget.expires
    budget.expires = min(original, time.monotonic() + 2)
    try:
        first = find(db, learner, games, color, board.fen(), item, budget)
        return first is None or first[0]["game_id"] != decision["game_id"]
    except (Exception, PreviewDeadline):
        return True
    finally:
        budget.expires = original
