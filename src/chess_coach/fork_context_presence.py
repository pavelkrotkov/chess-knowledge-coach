"""Bound matching proved fork opportunities in each independent game."""

from .fact_fingerprint import canonical


def pattern(root):
    features = root["features"]
    return canonical([features["mover"], features["target"], features["geometry"]])


def turn(turn, wanted):
    context = canonical([turn["side"], turn["time_control"], turn["phase"], turn["material"]])
    if context != wanted[0]:
        return False, False
    roots = turn["roots"]
    states = {
        root["state"] for root in roots if root["features"] is None or pattern(root) == wanted[1]
    }
    uncertain = "unknown" in states or turn["unsearched"] != 0 or turn["attempted"] != len(roots)
    return "proved" in states, uncertain
