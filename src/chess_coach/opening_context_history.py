"""Collect bounded, attributable early opening contexts from original games."""

from .opening_context_game import game as checked_game
from .opening_explore_recent import recent

PARENTS_PER_COLOR = 2


def sample(db, learner, budget):
    with budget.scope(snapshot=False):
        games, coverage = recent(db, learner)
    contexts = {"white": {}, "black": {}}
    observed = set()
    failed = 0
    checked = []
    for game, color in games:
        try:
            with budget.scope(snapshot=True):
                values, fingerprint = checked_game(db, learner, game, color)
        except (ValueError, TypeError, IndexError, StopIteration):
            failed += 1
            checked.append((game["id"], color, None))
            continue
        checked.append((game["id"], color, fingerprint))
        for parent, path, move in values:
            key = (parent, path)
            contexts[color][key] = contexts[color].get(key, 0) + 1
            observed.add((color, parent, move))
    incomplete = failed > 0 or any(coverage.values())
    return games, coverage, contexts, observed, failed, incomplete, checked


def ordered(contexts):
    values = sorted(contexts.items(), key=lambda item: (-item[1], item[0]))
    more = len(values) > PARENTS_PER_COLOR
    tied = more and values[PARENTS_PER_COLOR - 1][1] == values[PARENTS_PER_COLOR][1]
    return values[:PARENTS_PER_COLOR], max(0, len(values) - PARENTS_PER_COLOR), tied
