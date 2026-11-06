"""Check at most five current prepared protection sources."""

from .protection_plan_source import resolve

SOURCE_LIMIT = 5


def select(db, subject, ranked, budget):
    checked = 0
    for items in ranked:
        for item in items:
            if checked >= SOURCE_LIMIT:
                return None, checked
            budget.check()
            checked += 1
            try:
                source = resolve(db, subject, item)
            except (ValueError, TypeError, KeyError, IndexError):
                continue
            budget.check()
            return {
                **source,
                "games": len({x["game_key"] for x in items}),
                "markers": len(items),
            }, checked
    return None, checked
