"""Bound source-matched capture opportunity presence in independent games."""

from .fact_fingerprint import canonical


def pattern(turn, root):
    feature = root.get("features")
    if not feature:
        return None
    return canonical(
        [
            turn["side"],
            turn["time_control"],
            turn["phase"],
            turn["material"],
            root["mechanism"],
            feature["mover"],
            feature["target"],
            feature["geometry"],
        ]
    )


def _turn(turn, wanted):
    roots = turn["roots"]
    if any(root["state"] == "proved" and pattern(turn, root) == wanted[1] for root in roots):
        return "proved"
    context = canonical([turn["side"], turn["time_control"], turn["phase"], turn["material"]])
    if context != wanted[0]:
        return "outside"
    incomplete = turn["unsearched"] is None or turn["unsearched"] > 0
    incomplete |= turn["attempted"] > len(roots)
    if incomplete or any(
        root["state"] == "unknown" and pattern(turn, root) == wanted[1] for root in roots
    ):
        return "unknown"
    return "outside"


def sample(sample, wanted, check):
    turns = sample["root_details"]
    decisions = lower = upper = 0
    for game in sample["root_game_coverage"]:
        check()
        selected = [turn for turn in turns if turn["game_id"] == game["game_id"]]
        states = [_turn(turn, wanted) for turn in selected]
        hits = states.count("proved")
        decisions += hits
        found = hits > 0
        unknown = game["eligible"] > game["retained"] or "unknown" in states
        lower += found
        upper += found or unknown
    return {"decisions": decisions, "lower": lower, "upper": upper, "denominator": sample["games"]}
