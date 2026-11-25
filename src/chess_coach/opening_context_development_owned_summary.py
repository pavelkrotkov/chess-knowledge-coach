"""Qualify distinct reviewed games and their nominal chronology."""

from .mastery_time import parse_utc


def summary(found, excluded):
    games = {item["game_key"]: item for item in found}
    values = list(games.values())
    if len(values) < 2:
        return {
            "status": "withheld",
            "reason": "fewer_than_two_reviewed_miss_games",
            "observations": values,
            "excluded": dict(excluded),
        }
    times = [parse_utc(item["observation_at"]) for item in values]
    controls = {item["nominal_control"] for item in values}
    if len(set(times)) != len(times):
        return {"status": "withheld", "reason": "chronology_tied", "excluded": dict(excluded)}
    if len(controls) != 1 or "unknown" in controls:
        return {
            "status": "withheld",
            "reason": "nominal_context_mismatch",
            "excluded": dict(excluded),
        }
    return {
        "status": "supported",
        "games": len(values),
        "observations": values,
        "nominal_control": next(iter(controls)),
        "excluded": dict(excluded),
        "scope": "independent same-side reviewed fork-execution misses in the selected history",
    }
