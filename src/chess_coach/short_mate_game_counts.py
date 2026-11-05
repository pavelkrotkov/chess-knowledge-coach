"""Count resolved, unresolved, and unsearched game decisions."""

EXAMPLE_LIMIT = 20
OUTCOMES = (
    "immediate",
    "no_opportunity",
    "preserved",
    "missed",
    "opportunity_unresolved",
    "unknown",
)


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
    if (
        outcome in {"preserved", "missed", "opportunity_unresolved", "unknown"}
        and len(counts["examples"]) < EXAMPLE_LIMIT
    ):
        counts["examples"].append({"position_id": context["position_id"], "outcome": outcome})


def finish(counts):
    counts["unchecked"] = counts["eligible"] - sum(counts[key] for key in OUTCOMES)
    counts["complete"] = (
        counts["unchecked"] == counts["unknown"] == counts["opportunity_unresolved"] == 0
    )
    counts["opportunities"] = (
        counts["preserved"] + counts["missed"] + counts["opportunity_unresolved"]
    )
    return counts
