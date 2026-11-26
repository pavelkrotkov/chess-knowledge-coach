"""Retain optional exact roots from the existing fork classifier pass."""

from .capture_game_root_budget import record
from .short_mate_trend_turns import inspect as inspect_turns

POLICY = "knight-fork-game-roots-v1"


def start_details(details, board, played):
    if details is not None:
        details.update(
            side="white" if board.turn else "black",
            played=played,
            total=None,
            attempted=0,
            roots=[],
        )


def observe(observations, move, proof, state):
    if observations is not None:
        observations.append((move, proof, state))


def append_root(details, move, proof, state):
    if details is not None:
        details["attempted"] += 1
        if len(details["roots"]) < 32:
            details["roots"].append([move.uci(), proof["targets"] if proof else [], state])


def finish_details(details):
    if details is not None:
        total = details["total"]
        details["unsearched"] = None if total is None else total - details["attempted"]


def inspect(db, learner, item, deadline, quota, *, state, classifier, seconds):
    from .fork_game_proof import VERSION

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
