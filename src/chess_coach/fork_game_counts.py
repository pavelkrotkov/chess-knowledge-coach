"""Count proved and unresolved supported forks without inferring mistakes."""

from .fork_game_trend_validate import OUTCOMES

EXAMPLE_LIMIT = 20


def empty(eligible):
    return {
        "eligible": eligible,
        **dict.fromkeys(OUTCOMES, 0),
        "unresolved_roots": 0,
        "examples": [],
        "_other_examples": [],
    }


def add(counts, position, outcome, reason):
    counts[outcome] += 1
    if reason == "unresolved_roots":
        counts["unresolved_roots"] += 1
    if outcome == "no_candidate":
        return
    key = "examples" if outcome in {"played", "awaiting"} else "_other_examples"
    if len(counts[key]) < EXAMPLE_LIMIT:
        counts[key].append({"position_id": position, "outcome": outcome})


def finish(counts):
    counts["examples"] = (counts["examples"] + counts.pop("_other_examples"))[:EXAMPLE_LIMIT]
    counts["scanned"] = sum(counts[key] for key in OUTCOMES)
    counts["unchecked"] = counts["eligible"] - counts["scanned"]
    counts["opportunities"] = counts["played"] + counts["awaiting"]
    return counts


def sample(games):
    result = empty(sum(item["eligible"] for item in games))
    result["games"] = len(games)
    result["newest"] = games[0]["date"] if games else None
    result["oldest"] = games[-1]["date"] if games else None
    for game in games:
        for position, outcome, reason in game["results"]:
            add(result, position, outcome, reason)
    return finish(result)
