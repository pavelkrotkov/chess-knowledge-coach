"""Bound source-matched capture opportunity presence in independent games."""

from .fact_fingerprint import canonical


def pattern(root):
    feature = root["features"]
    return canonical(
        [
            root["mechanism"],
            feature["mover"],
            feature["target"],
            feature["geometry"],
        ]
    )


def _turn(turn, wanted):
    context = canonical([turn["side"], turn["time_control"], turn["phase"], turn["material"]])
    if context != wanted[0]:
        return False, False
    roots = turn["roots"]
    states = {root["state"] for root in roots if pattern(root) == wanted[1]}
    uncertain = "unknown" in states or turn["unsearched"] != 0 or turn["attempted"] != len(roots)
    return "proved" in states, uncertain


def sample(sample, wanted, check):
    decisions = lower = upper = 0
    for game in sample["root_game_coverage"]:
        check()
        states = [_turn(turn, wanted) for turn in game["turns"]]
        hits = sum(found for found, _ in states)
        decisions += hits
        found = hits > 0
        unknown = game["eligible"] > len(states) or any(unknown for _, unknown in states)
        lower += found
        upper += found or unknown
    return {
        "decisions": decisions,
        "lower": lower,
        "upper": upper,
        "denominator": sample["games"],
        "qualified": decisions >= 5 and lower >= 3,
    }
