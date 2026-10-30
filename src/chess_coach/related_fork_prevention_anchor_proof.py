"""Charge anchored fork proof attempts against local and shared limits."""

from .fork_defense_anchor import MAX_PROOFS
from .fork_defense_anchor_match import find_fork


def prove(after, candidates, budget, local_proofs):
    remaining = min(MAX_PROOFS - local_proofs, budget["proof_limit"] - budget["proofs"])
    proof, left = find_fork(after, candidates, remaining)
    used = remaining - max(0, left)
    budget["proofs"] += used
    if left < 0:
        budget["truncated"] = True
    return proof, local_proofs + used
