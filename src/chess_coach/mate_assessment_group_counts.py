"""Count outcomes and assistance separately within a sample."""

from collections import Counter


def _outcomes(items, assisted):
    return dict(
        Counter(
            item["outcome"]
            for item in items
            if item["hints"] is not None and bool(item["hints"]) == assisted
        )
    )


def counts(items):
    return {
        "size": len(items),
        "outcomes": dict(Counter(item["outcome"] for item in items)),
        "hinted": sum(
            item["hints"] is not None and item["hints"] > item["reveals"] for item in items
        ),
        "revealed": sum(item["reveals"] is not None and item["reveals"] > 0 for item in items),
        "unassisted": _outcomes(items, False),
        "assisted": _outcomes(items, True),
        "start": items[0]["started_at"] if items else None,
        "end": items[-1]["started_at"] if items else None,
    }
