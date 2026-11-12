"""Cheaply nominate a bounded same-kind counterfactual pin."""

from .fork_defense_safety import quiet_after
from .objective_pin_prevent_created import _prepare
from .related_pin_created_geometry import geometry


def nominate(board, bad, source, budget):
    after = quiet_after(board, bad)
    if after is None:
        return None
    candidates = geometry(after)
    if candidates is None:
        budget["unknown"] += 1
        return None
    if not any(pin["type"] == source["pin_kind"] for _move, pin in candidates):
        return None
    after, reason = _prepare(board, bad)
    if reason:
        budget["unknown"] += 1
        return None
    return after, candidates
