"""Validate capture cache relationships before trusting derived results."""

from .capture_game_counts import OUTCOMES
from .capture_game_trend_relations import valid_relations
from .short_mate_trend_validate import valid


def validate(data, expected):
    if not valid(data, expected, outcomes=OUTCOMES):
        return False
    checked = data["checked"]
    if len({row[0] for row in checked}) != len(checked):
        return False
    if min(data["duplicates"], data["unavailable"]) < 0:
        return False
    if len(data["games"]) + data["duplicates"] + data["unavailable"] != len(checked):
        return False
    return valid_relations(data, checked)


def matches_frontier(data, candidates):
    checked = [row[0] for row in data["checked"]]
    actual = [game["id"] for game, _ in candidates]
    if checked != actual[: len(checked)]:
        return False
    complete = len(data["games"]) >= 41 or len(checked) == len(actual)
    return data["selection_complete"] == complete
