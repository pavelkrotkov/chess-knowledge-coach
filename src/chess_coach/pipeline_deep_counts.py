"""Count selected, capped and current job outcomes for one selection."""

from collections import Counter


def selection_counts(selection):
    counts = Counter(
        {"selected": len(selection["items"]), "capped_out": selection["coverage"]["capped_out"]}
    )
    for item in selection["items"]:
        status = item["status"]
        counts["pending" if status in {"pending_deep", "pending", "running"} else status] += 1
    return counts
