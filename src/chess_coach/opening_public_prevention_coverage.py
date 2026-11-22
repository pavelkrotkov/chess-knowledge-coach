"""Track disjoint per-origin outcomes and shared-limit interruptions."""

ORIGINS = ("pre_existing", "created")


def empty():
    return {
        "supported": 0,
        "unsupported": 0,
        "incomplete": 0,
        "completed_without_example": 0,
        "ended_before_window": 0,
        "example": None,
    }


def record(result, found, censored):
    result["censored"] += int(censored)
    for origin, (status, example) in found.items():
        result["origins"][origin][status] += 1
        if example is not None and result["origins"][origin]["example"] is None:
            result["origins"][origin]["example"] = example


def remaining(result, count, reason):
    result["status"] = "incomplete"
    result["interrupted"] = reason == "deadline"
    result["proof_limit"] = reason == "proof_limit"
    for origin in ORIGINS:
        result["origins"][origin]["incomplete"] += count


def finish(result):
    for value in result["origins"].values():
        value["analyzed"] = value["supported"] + value["completed_without_example"]
    if any(value["incomplete"] for value in result["origins"].values()):
        result["status"] = "incomplete"
    return result
