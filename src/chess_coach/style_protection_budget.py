"""Cap source resolutions and material proofs across one report."""

MAX_WORK = 20


def create(*, limit=MAX_WORK):
    return {
        "limit": limit,
        "used": 0,
        "considered": 0,
        "lookups": 0,
        "resolutions": 0,
        "probes": 0,
        "proofs": 0,
        "skipped": 0,
        "skipped_decisions": 0,
        "no_source": 0,
        "multiple_sources": 0,
        "unsupported": 0,
        "completed": 0,
    }


def take(budget, kind):
    if budget["used"] >= budget["limit"]:
        budget["skipped"] += 1
        return False
    budget["used"] += 1
    budget[kind] += 1
    return True
