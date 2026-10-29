"""Allocate nominated categories, filling unused slots with controls."""

from .deep_selection_categories import categories
from .deep_selection_quotas import rotated


def fill(selected, seen, ordered, limit, game_key):
    while len(selected) < limit:
        added = False
        for category in rotated(game_key):
            item = _next_candidate(ordered, seen, category)
            if item is None:
                continue
            selected.append({**item, "allocation": category})
            seen.add(item["position_id"])
            added = True
            if len(selected) >= limit:
                return
        if not added:
            _fill_controls(selected, seen, ordered, limit)
            return


def _fill_controls(selected, seen, ordered, limit):
    for item in ordered:
        if len(selected) >= limit:
            return
        if item["position_id"] not in seen:
            selected.append({**item, "allocation": "control"})
            seen.add(item["position_id"])


def _next_candidate(ordered, seen, category):
    return next(
        (
            item
            for item in ordered
            if item["position_id"] not in seen and category in categories(item["reasons"])
        ),
        None,
    )
