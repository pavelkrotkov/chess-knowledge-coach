"""Account for conditional mate work within one read-only report."""


def reserve(budget):
    if budget is None:
        return True
    if budget["examined"] >= budget["limit"]:
        budget["skipped"] += 1
        return False
    budget["examined"] += 1
    return True


def record(budget, result):
    if budget is not None:
        key = "completed" if result["status"] == "complete" else "unsupported"
        budget[key] += 1
