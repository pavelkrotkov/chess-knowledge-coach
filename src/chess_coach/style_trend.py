"""Compare game-start groups without implying decision-time ordering."""

from .style_counts import counts


def _periods(items):
    dates = [item["context"]["game_start_at"] for item in items]
    if None in dates:
        return None
    unique = sorted(set(dates))
    if len(unique) < 2:
        return None
    boundary = unique[len(unique) // 2]
    return (
        boundary,
        [item for item in items if item["context"]["game_start_at"] < boundary],
        [item for item in items if item["context"]["game_start_at"] >= boundary],
    )


def trend(items, dimension):
    periods = _periods(items)
    if periods is None:
        return None
    boundary, earlier, later = periods
    old, new = counts(earlier, dimension), counts(later, dimension)
    if not old["sufficient"] or not new["sufficient"]:
        return None
    return {"game_start_boundary": boundary, "earlier": old, "later": new}
