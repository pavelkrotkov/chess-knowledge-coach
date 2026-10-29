"""Collect comparable selected decisions for one attributable game."""

from collections import Counter

from .style_game_observations import collect
from .style_selection import selection_coverage


def game_observations(db, learner, game, selected):
    counts, allocations, observations = Counter(), Counter(), []
    if selected is None:
        return counts, allocations, observations
    by_id, missing, selection_allocations = _selection_index(selected, game["contexts"])
    counts["selected"] += len(by_id)
    counts["selected_without_learner_context"] += missing
    allocations.update(selection_allocations)
    if selected["state"] != "current":
        counts["stale_selection"] += len(by_id)
        return counts, allocations, observations
    counts.update(selection_coverage(selected))
    collect(db, learner, game, selected, by_id, counts, observations)
    return counts, allocations, observations


def _selection_index(selected, contexts):
    by_id = {item["position_id"]: item for item in selected["items"]}
    context_ids = {context["position_id"] for context in contexts}
    return by_id, len(by_id.keys() - context_ids), [item["allocation"] for item in by_id.values()]
