"""Count complete legal response sets and recorded choices."""


def record(counts, item):
    counts["checks"] += 1
    count = item["legal_responses"]
    counts["terminal_mate"] += int(item["checkmate"])
    counts["one_response"] += int(count == 1)
    counts["multiple_responses"] += int(count > 1)
    for kind, amount in item["response_classes"].items():
        counts["legal_" + kind] += int(amount > 0)
    if item["played"]:
        counts["played_" + item["played"]["kind"]] += 1


def totals(counts, selected, example):
    statuses = ("ended", "frontier", "cutoff", "unsupported", "unavailable")
    incomplete = selected - sum(counts[key] for key in statuses)
    keys = (
        *statuses,
        "checked_games",
        "unanswered",
        "checks",
        "terminal_mate",
        "one_response",
        "multiple_responses",
        "legal_king",
        "legal_capture",
        "legal_interposition",
        "played_king",
        "played_capture",
        "played_interposition",
    )
    return {
        "status": "incomplete" if incomplete else "complete",
        "selected": selected,
        "analyzed": counts["ended"] + counts["frontier"] + counts["cutoff"],
        "censored": counts["frontier"] + counts["cutoff"],
        "preparation_incomplete": incomplete,
        "interrupted": bool(incomplete),
        **{key: counts[key] for key in keys},
        "example": example,
    }
