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
