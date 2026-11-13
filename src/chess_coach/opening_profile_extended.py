"""Summarize the longer view without changing the legacy course profile."""

from collections import Counter

from .named_structures import definitions
from .opening_profile_game import project


def _families(items):
    counts, later = Counter(), Counter()
    for item in items:
        counts.update(item["extended"])
        later.update(item["extended"] - item["early"])
    names = definitions()
    families = [
        {
            "family": family,
            "color": color,
            "count": count,
            "later_only": later[(family, color)],
            **names[family],
        }
        for (family, color), count in sorted(counts.items())
    ]
    return families


def _items(db, selected):
    return [project(db, game_id, first) for game_id, first in selected]


def summarize(db, selected):
    items = _items(db, selected)
    families = _families(items)
    spans = [item["span"] for item in items]
    early = [item["early_span"] for item in items]
    return {
        "min_span": min(early, default=0),
        "max_span": max(early, default=0),
        "extended": {
            "games": len(items),
            "families": families,
            "no_supported_match": sum(not item["extended"] for item in items),
            "window_cutoffs": sum(item["cutoff"] for item in items),
            "frontier_windows": sum(item["frontier"] for item in items),
            "ended_windows": sum(item["ended"] for item in items),
            "min_span": min(spans, default=0),
            "max_span": max(spans, default=0),
        },
        "examples": [item["example"] for item in items],
    }
