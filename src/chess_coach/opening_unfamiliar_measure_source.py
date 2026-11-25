"""Find a verified owned decision at an experiment's exact first-turn parent."""

from .opening_unfamiliar_measure_decision import candidate


def candidates(db, learner, games, color, parent, suggestion, budget, *, path=None):
    for game, side in games:
        if side != color:
            continue
        try:
            with budget.scope(snapshot=False):
                found = candidate(db, learner, game["id"], color, parent, suggestion, path=path)
            if found:
                yield found
        except (ValueError, TypeError, IndexError, StopIteration):
            continue


def find(db, learner, games, color, parent, suggestion, budget, *, path=None):
    return next(candidates(db, learner, games, color, parent, suggestion, budget, path=path), None)


def first_game(games, color):
    return next((game["id"] for game, side in games if side == color), None)
