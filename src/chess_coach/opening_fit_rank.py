"""Compare conservative coverage ranges for exact public branches."""

from fractions import Fraction

MIN_PUBLIC = 5
MIN_GAP = Fraction(1, 2)


def bounds(item, public):
    if item["profile"]["center"]["valid"] < MIN_PUBLIC or public["valid"] < MIN_PUBLIC:
        return None
    total, valid, available = public["sampled"], public["valid"], public["available"]
    if not total:
        return None
    return Fraction(available, total), Fraction(available + total - valid, total)


def _qualified(items, public):
    result = []
    for item in items:
        record = public.get(item["uci"])
        interval = bounds(item, record) if record else None
        if interval is not None:
            result.append((item["uci"], interval))
    return result


def rank(items, public, owned):
    qualified = _qualified(items, public)
    if not owned.get("positive") or len(qualified) < 2:
        return None
    for move, (lower, _) in qualified:
        others = [upper for name, (_, upper) in qualified if name != move]
        if all(lower - upper >= MIN_GAP for upper in others):
            return move
    return None
