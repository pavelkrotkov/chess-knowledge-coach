"""Validate cached games and their bounded decision results."""

from .short_mate_game_counts import OUTCOMES


# A malformed sidecar never becomes game evidence; the worker rebuilds it.
def _result(row, outcomes=OUTCOMES):
    if not isinstance(row, list) or len(row) != 3:
        return False
    position, outcome, reason = row
    return (
        type(position) is int
        and position > 0
        and outcome in outcomes
        and (reason is None or isinstance(reason, str))
    )


def _eligible(item, outcomes=OUTCOMES):
    eligible, results = item.get("eligible"), item.get("results")
    if type(eligible) is not int or not 0 <= eligible <= 500:
        return False
    return (
        isinstance(results, list)
        and len(results) <= eligible
        and all(_result(row, outcomes) for row in results)
    )


def game(item, outcomes=OUTCOMES):
    if not isinstance(item, dict):
        return False
    if type(item.get("id")) is not int or item["id"] <= 0:
        return False
    if not all(isinstance(item.get(k), str) for k in ("date", "identity", "signature")):
        return False
    return _eligible(item, outcomes)


def games(value, outcomes=OUTCOMES):
    return (
        isinstance(value, list) and len(value) <= 41 and all(game(item, outcomes) for item in value)
    )


def retained(value, outcomes=OUTCOMES):
    return (
        isinstance(value, dict)
        and len(value) <= 41
        and all(game(item, outcomes) for item in value.values())
    )
