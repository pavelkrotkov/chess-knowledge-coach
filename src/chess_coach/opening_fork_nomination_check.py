"""Validate selected owned-game fork evidence against its current source."""

from .objective_source_budget import MAX_GAME_BYTES
from .opening_profile_owned_control import control
from .recurrence_candidates import candidate
from .recurrence_counts import counts
from .recurrence_game_cache import source
from .style_time_query import load_game


def checked(db, learner, row, selected, cache, parts, excluded):
    game = source(db, learner, row, selected, cache, excluded)
    if game is None or game["key"] != selected[row["game_id"]]["game_key"]:
        return None
    item, reason = candidate(db, row, game, parts)
    if reason or item["currentness"] != "marker matches; proof not replayed":
        return None
    if item["review"] not in {"accepted", "unreviewed"}:
        return None
    return {**item, "nominal_control": control(game["row"])}


def binding_control(db, game_id, budget):
    with budget.scope(snapshot=False):
        game = load_game(db.connection, game_id, max_game_bytes=MAX_GAME_BYTES)
        return control(game) if game is not None else "unknown"


def summary(items, nominal):
    values = counts(items)
    if values["miss_games"] < 2:
        return {"status": "withheld", "reason": "fewer_than_two_independent_miss_games"}
    if nominal == "unknown" or {item["nominal_control"] for item in items} != {nominal}:
        return {"status": "withheld", "reason": "nominal_context_mismatch"}
    return {
        "status": "provisional" if values["review"].get("unreviewed") else "supported",
        **values,
        "nominal_control": nominal,
        "observations": items,
    }
