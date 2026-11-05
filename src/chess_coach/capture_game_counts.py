"""Count complete, unresolved, and unsearched capture decisions."""

OUTCOMES = ("no_opportunity", "played", "other", "opportunity_unresolved", "unknown")
EXAMPLE_LIMIT = 20


def empty(eligible):
    return {
        "eligible": eligible,
        "checked": 0,
        **dict.fromkeys(OUTCOMES, 0),
        "examples": [],
        "_unresolved_examples": [],
        "reasons": {},
    }


def add(counts, context, outcome, reason, board=None):
    counts[outcome] += 1
    if outcome not in {"unknown", "opportunity_unresolved"}:
        counts["checked"] += 1
    if reason:
        counts["reasons"][reason] = counts["reasons"].get(reason, 0) + 1
    if outcome in {"played", "other", "opportunity_unresolved"}:
        key = "_unresolved_examples" if outcome == "opportunity_unresolved" else "examples"
        if len(counts[key]) < EXAMPLE_LIMIT:
            item = {"position_id": context["position_id"], "outcome": outcome}
            if board is not None:
                item["played_san"] = board.san(board.parse_uci(context["played_move"]))
            counts[key].append(item)


def finish(counts):
    counts["examples"] = (counts["examples"] + counts.pop("_unresolved_examples"))[:EXAMPLE_LIMIT]
    counts["unchecked"] = counts["eligible"] - sum(counts[key] for key in OUTCOMES)
    counts["complete"] = (
        counts["unchecked"] == counts["unknown"] == counts["opportunity_unresolved"] == 0
    )
    counts["opportunities"] = counts["played"] + counts["other"] + counts["opportunity_unresolved"]
    return counts
