"""Retain only usable ranked scout nominations from the restricted root set."""

from .purpose_config import SCOUT_NODES
from .purpose_lines import roots, work


def choose(candidates, raw, error, items, invalid):
    allowed = {move.uci() for move in candidates}
    usable = [item for item in items if item["line"]["root_move"] in allowed]
    result = {"lines": usable, "work": work(raw, SCOUT_NODES)}
    if error:
        return result, None, error
    if not usable:
        return result, None, "invalid_scout" if invalid else "no_distinct_nominee"
    if not distinct(usable):
        return result, None, "invalid_scout"
    return result, roots(usable)[0], None


def distinct(items):
    return len(items) <= 2 and len(set(roots(items))) == len(items)
