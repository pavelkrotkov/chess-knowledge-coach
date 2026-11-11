"""Summarize verified first-encounter samples without grading unknown moves."""

from collections import Counter


def sample(items):
    counts = Counter(item["status"] for item in items)
    unassisted = Counter(item["status"] for item in items if item.get("hints") == 0)
    total = sum(unassisted[key] for key in ("correct", "incorrect", "unresolved"))
    return {
        "items": items,
        "start": items[0]["started_at"],
        "end": items[-1]["started_at"],
        "size": len(items),
        "counts": counts,
        "assisted": sum(bool(item.get("hints")) for item in items),
        "assistance_unknown": sum(item.get("hints") is None for item in items),
        "unassisted": unassisted,
        "total": total,
        "low": unassisted["correct"],
        "high": unassisted["correct"] + unassisted["unresolved"],
    }
