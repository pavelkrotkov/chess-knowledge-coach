"""Require two complete, independent samples before comparing."""

SAMPLE = 10


def _sufficient_unassisted(sample):
    return sum(not item["hints"] for item in sample) >= 5


def _ordered(items):
    return (
        items[SAMPLE - 1]["started_at"] < items[SAMPLE]["started_at"]
        and items[-SAMPLE - 1]["started_at"] < items[-SAMPLE]["started_at"]
    )


def comparable(items, limited):
    if limited or len(items) < 2 * SAMPLE:
        return False
    earlier, later = items[:SAMPLE], items[-SAMPLE:]
    if not _ordered(items):
        return False
    if any(
        not item["current"] or item["outcome"] not in {"verified", "incorrect"}
        for item in earlier + later
    ):
        return False
    return _sufficient_unassisted(earlier) and _sufficient_unassisted(later)
