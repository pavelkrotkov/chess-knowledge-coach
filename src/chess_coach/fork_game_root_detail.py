"""Retain optional exact roots from the existing fork classifier pass."""

from .capture_game_root_budget import record
from .fork_game_proof import VERSION
from .short_mate_trend_turns import inspect as inspect_turns

POLICY = "knight-fork-game-roots-v1"


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
        record(state, item, row, detail, version=POLICY, proof=VERSION)
    return used
