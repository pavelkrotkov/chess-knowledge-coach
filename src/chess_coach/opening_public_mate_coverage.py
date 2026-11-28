"""Keep per-game and branch mate coverage in one shared contract."""

from .opening_public_fork_windows import bounds

COUNTERS = (
    "analyzed",
    "supported",
    "unsupported",
    "ended_before_window",
    "preparation_incomplete",
)


def observation(censored, *, example=None, analyzed=False, ended=False, incomplete=False):
    return {
        **dict.fromkeys(COUNTERS, 0),
        "censored": int(censored),
        "analyzed": int(analyzed),
        "supported": int(example is not None),
        "ended_before_window": int(ended),
        "preparation_incomplete": int(incomplete),
        "example": example,
    }


def unavailable(reason):
    return {"status": "incomplete", "reason": reason, "eligible": None, "selected": None}


def coverage(context, selected, more, binding):
    return {
        **dict.fromkeys(COUNTERS, 0),
        "status": "prepared",
        "eligible": context["matched_candidates"],
        "selected": len(selected),
        "censored": sum(
            row[1] > bounds(binding["ply"], row[1], binding["policy"]["mate"]["window"])[1]
            for row in selected
        ),
        "excluded_context": context["excluded_context"],
        "unknown_context": context["unknown_context"],
        "more_eligible": more,
        "interrupted": False,
        "example": None,
    }


def record(result, item):
    for key in COUNTERS:
        result[key] += item[key]
    if result["example"] is None:
        result["example"] = item["example"]


def finish(result, remaining=0):
    if remaining:
        result["interrupted"] = True
        result["preparation_incomplete"] += remaining
    if result["preparation_incomplete"] or result["interrupted"]:
        result["status"] = "incomplete"
    return result
