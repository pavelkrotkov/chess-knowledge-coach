"""Retain exact-root detail from the existing capture scan."""

from .capture_game_root_budget import record
from .short_mate_trend_turns import inspect as inspect_turns


def inspect(db, learner, item, deadline, quota, *, state, classifier, seconds):
    collected = []

    def classify(board, played, until, clock):
        detail = {}
        result = classifier(board, played, until, clock, details=detail)
        collected.append(detail)
        return result

    first = len(item["results"])
    used = inspect_turns(db, learner, item, deadline, quota, classifier=classify, seconds=seconds)
    for row, detail in zip(item["results"][first:], collected, strict=False):
        if detail:
            record(state, item, row, detail)
    return used
