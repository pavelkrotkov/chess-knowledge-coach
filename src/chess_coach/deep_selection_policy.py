"""Allocate bounded candidate and control slots reproducibly."""

from .deep_selection_allocator import fill
from .deep_selection_coverage import coverage
from .deep_selection_quotas import targets
from .deep_selection_sampling import controls, sample_key


def select_positions(candidates, game_key, limit):
    ordered = sorted(candidates, key=lambda item: sample_key(game_key, item))
    chosen_controls = controls(ordered, limit)
    selected = [{**item, "allocation": "control"} for item in chosen_controls]
    seen = {item["position_id"] for item in selected}
    quota_targets = targets(min(limit, len(ordered)) - len(chosen_controls), game_key)
    fill(selected, seen, ordered, limit, game_key)
    for item in selected:
        if item["allocation"] == "control":
            item["reasons"] = sorted({*item["reasons"], "control_sample"})
    return selected, coverage(ordered, selected, quota_targets, len(chosen_controls), limit)
