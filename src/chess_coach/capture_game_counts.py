"""Count complete, unresolved, and unsearched capture decisions."""

OUTCOMES = ("no_opportunity", "played", "other", "opportunity_unresolved", "unknown")
EXAMPLE_LIMIT = 20


def empty(eligible):
    return {
        "eligible": eligible,
        "checked": 0,
        **dict.fromkeys(OUTCOMES, 0),
        "examples": [],
        "reasons": {},
    }


def add(counts, context, outcome, reason):
    counts[outcome] += 1
    if outcome not in {"unknown", "opportunity_unresolved"}:
        counts["checked"] += 1
    if reason:
        counts["reasons"][reason] = counts["reasons"].get(reason, 0) + 1
    if outcome != "no_opportunity" and len(counts["examples"]) < EXAMPLE_LIMIT:
        counts["examples"].append({"position_id": context["position_id"], "outcome": outcome})


def finish(counts):
    counts["unchecked"] = counts["eligible"] - sum(counts[key] for key in OUTCOMES)
    counts["complete"] = (
        counts["unchecked"] == counts["unknown"] == counts["opportunity_unresolved"] == 0
    )
    counts["opportunities"] = counts["played"] + counts["other"] + counts["opportunity_unresolved"]
    return counts
