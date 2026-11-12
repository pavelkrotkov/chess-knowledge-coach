"""Find a verified owned decision at an experiment's exact first-turn parent."""

from .opening_unfamiliar_measure_decision import candidate


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
