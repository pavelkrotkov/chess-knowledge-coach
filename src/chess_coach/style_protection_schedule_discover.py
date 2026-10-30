"""Limit proof discovery work without changing the ordinary scan budget."""

from .style_protection_schedule_binding import capture
from .style_protection_schedule_candidates import select

HISTORY_LIMIT = 500


def discover(db, learner, key, candidates, slots, budget):
    item = select(db, learner, key, candidates, slots)
    before = budget["used"]
    original_limit = budget["limit"]
    budget["limit"] = min(original_limit, before + HISTORY_LIMIT)
    try:
        binding, reason = capture(db, learner, item)
    finally:
        budget["limit"] = original_limit
    return item, binding, reason, budget["used"] - before
