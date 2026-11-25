"""Attach bounded public response distance to the existing context inventory."""

from .opening_distance_tree import distance


def enrich(items, sample, budget, index):
    for item in items:
        if item["source"] is None:
            item["distance"] = {"status": "unavailable"}
        else:
            item["distance"] = distance(index, item["selection"], sample, budget)
