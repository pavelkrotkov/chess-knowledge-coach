"""Validate a particular counterfactual after reserving bounded proof work."""

from .fork_defense_safety import quiet_after, safe_material
from .fork_defense_scan import MAX_CANDIDATES, scan
from .related_fork_avoidance_prefilter import possible
from .related_fork_avoidance_proof import pick
from .related_fork_prevention_budget import take


def alternative(board, good, bad, before, source, budget):
    after = quiet_after(board, bad)
    if after is None:
        return None
    if not safe_material(after):
        budget["unknown"] += 1
        return None
    possible_shape = possible(board, good, bad, after, before, source)
    if possible_shape is None:
        budget["unknown"] += 1
        return None
    if not possible_shape:
        return None
    if not take(budget, "proofs", MAX_CANDIDATES):
        return None
    result = scan(after)
    if result is None or result["uncertain"]:
        budget["unknown"] += 1
        return None
    return pick(board, good, bad, after, before, source, result["proven"].values())
