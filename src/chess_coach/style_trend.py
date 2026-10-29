"""Compare disjoint dated periods only when each is sufficiently sampled."""

from .style_counts import counts


def _periods(items):
    dates = [item["context"]["observed_at"] for item in items]
    if None in dates:
        return None
    unique = sorted(set(dates))
    if len(unique) < 2:
        return None
    boundary = unique[len(unique) // 2]
    return (
        boundary,
        [item for item in items if item["context"]["observed_at"] < boundary],
        [item for item in items if item["context"]["observed_at"] >= boundary],
    )


def trend(items, dimension):
    periods = _periods(items)
    if periods is None:
        return None
    boundary, earlier, later = periods
    old, new = counts(earlier, dimension), counts(later, dimension)
    if not old["sufficient"] or not new["sufficient"]:
        return None
    return {"boundary": boundary, "earlier": old, "later": new}
