"""Recheck one game's source while advancing its exposure sample."""

from .created_exposure_game_sample import advance, finished
from .protection_game_review import binding as review_binding
from .protection_game_source import binding as analysis_binding
from .protection_game_source import prepare
from .short_mate_game_source import recheck
from .short_mate_trend_cohort import fingerprint
from .short_mate_trend_turns import _check_prefix


def _source(db, learner, item):
    source = prepare(db, learner, item["id"])
    if fingerprint(source["signature"]) != item["signature"]:
        raise ValueError("game changed")
    return source


def inspect(db, learner, item, deadline, quota, *, profile):
    analysis = analysis_binding(db, item["id"])
    review, blocked = review_binding(db, item["id"], learner)
    stamps = (analysis, review)
    previous = (item.get("analysis"), item.get("review"))
    if previous == stamps and (finished(item) or len(item["results"]) == item["eligible"]):
        return 1
    source = _source(db, learner, item)
    turns = [(context, board) for context, board in source["pairs"] if context["subject"]]
    if previous != stamps:
        item["results"] = []
    _check_prefix(item, turns)
    used = advance(item, turns, blocked, profile, deadline, quota)
    recheck(db, learner, source)
    if (analysis_binding(db, item["id"]), review_binding(db, item["id"], learner)[0]) != stamps:
        raise ValueError("sources changed during inspection")
    item["analysis"], item["review"] = stamps
    return max(used, 1)
