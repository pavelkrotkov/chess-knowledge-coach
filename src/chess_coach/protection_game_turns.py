"""Advance a bounded slice of independently replayed protection decisions."""

import time

from .protection_game_proof import classify
from .protection_game_review import binding as review_binding
from .protection_game_source import binding as analysis_binding
from .protection_game_source import prepare
from .short_mate_game_source import recheck
from .short_mate_trend_cohort import fingerprint
from .short_mate_trend_turns import _check_prefix, _reason

TURN_SECONDS = 0.5


def _result(context, board, blocked, deadline):
    position = context["position_id"]
    if position in blocked:
        return [position, "unknown", "source_unavailable"]
    local = min(time.monotonic() + TURN_SECONDS, deadline)
    outcome, reason = classify(board, context["played_move"], local, time.monotonic)
    reason = _reason(reason, local, deadline)
    return None if reason == "cycle_deadline" else [position, outcome, reason]


def _advance(item, turns, blocked, deadline, quota):
    used = 0
    while used < quota and len(item["results"]) < len(turns):
        if time.monotonic() + TURN_SECONDS >= deadline:
            break
        result = _result(*turns[len(item["results"])], blocked, deadline)
        if result is None:
            break
        item["results"].append(result)
        used += 1
    return used


def inspect(db, learner, item, deadline, quota):
    analysis = analysis_binding(db, item["id"])
    review, blocked = review_binding(db, item["id"], learner)
    stamps = (analysis, review)
    previous = (item.get("analysis"), item.get("review"))
    if previous == stamps and len(item["results"]) == item["eligible"]:
        return 1
    source = prepare(db, learner, item["id"])
    if fingerprint(source["signature"]) != item["signature"]:
        raise ValueError("game changed")
    turns = [(context, board) for context, board in source["pairs"] if context["subject"]]
    # A source change invalidates only this game and restarts its proof prefix.
    if previous != stamps:
        item["results"] = []
    _check_prefix(item, turns)
    used = _advance(item, turns, blocked, deadline, quota)
    # Recheck after proof so a changing source cannot bless new outcomes.
    recheck(db, learner, source)
    if (analysis_binding(db, item["id"]), review_binding(db, item["id"], learner)[0]) != stamps:
        raise ValueError("sources changed during inspection")
    item["analysis"], item["review"] = stamps
    return max(used, 1)
