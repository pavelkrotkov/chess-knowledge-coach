"""Validate private fork scan records and their source relationships."""

from .capture_game_trend_validate import validate as capture_validate
from .fork_game_root_validate import valid as valid_roots

OUTCOMES = ("no_candidate", "played", "awaiting", "unresolved", "unknown")
REASONS = {
    "no_candidate": {None},
    "played": {None, "unresolved_roots"},
    "awaiting": {None, "unresolved_roots"},
    "unresolved": {"unresolved_roots"},
    "unknown": {"unsupported_position", "turn_deadline"},
}


def validate(data, expected):
    if not capture_validate(data, expected, outcomes=OUTCOMES):
        return False
    games = [*data["games"], *data["retained"].values()]
    if data.get("prior"):
        games.extend(data["prior"]["games"])
    return valid_roots(data) and all(
        reason in REASONS[outcome] for game in games for _, outcome, reason in game["results"]
    )
