"""Validate one reviewed owned fork-execution observation."""

from .mastery_time import parse_utc
from .opening_fit_owned_summary import _control
from .recurrence_candidates import candidate
from .recurrence_game_cache import source


def observation(db, learner, row, selected, color, cache, parts, excluded):
    game = source(db, learner, row, selected, cache, excluded)
    if game is None or game["color"] != color:
        excluded["game_unavailable_or_other_side"] += 1
        return None
    item, reason = candidate(db, row, game, parts)
    if reason or item["currentness"] != "marker matches; proof not replayed":
        excluded["source_unavailable"] += 1
        return None
    if item["review"] != "accepted":
        excluded["review_not_accepted"] += 1
        return None
    when = item["decision"]["observation_at"]
    if parse_utc(when) is None:
        excluded["chronology_unknown"] += 1
        return None
    return {
        "evidence_id": item["id"],
        "game_id": item["game_id"],
        "position_id": item["position_id"],
        "game_key": item["game_key"],
        "observation_at": when,
        "review": item["review"],
        "currentness": item["currentness"],
        "nominal_control": _control(game["row"]["time_control"]),
    }
