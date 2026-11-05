"""Check a bounded slice of one replayed game's learner turns."""

import time

from .short_mate_game_proof import classify
from .short_mate_game_source import prepare, recheck
from .short_mate_trend_cohort import fingerprint

TURN_SECONDS = 0.5


def _reason(reason, local, deadline):
    if reason != "deadline":
        return reason
    return "cycle_deadline" if local == deadline else "turn_deadline"


def _evaluate(board, played, deadline, classifier):
    return (classifier or classify)(board, played, deadline, time.monotonic)


def inspect(db, learner, item, deadline, quota, *, classifier=None, seconds=TURN_SECONDS):
    source = prepare(db, learner, item["id"])
    if fingerprint(source["signature"]) != item["signature"]:
        raise ValueError("game changed")
    turns = [(context, board) for context, board in source["pairs"] if context["subject"]]
    used = 0
    while len(item["results"]) < len(turns) and used < quota:
        if time.monotonic() + seconds >= deadline:
            break
        context, board = turns[len(item["results"])]
        local = min(time.monotonic() + seconds, deadline)
        outcome, reason = _evaluate(board, context["played_move"], local, classifier)
        reason = _reason(reason, local, deadline)
        if reason == "cycle_deadline":
            break
        item["results"].append([context["position_id"], outcome, reason])
        used += 1
    recheck(db, learner, source)
    return used
