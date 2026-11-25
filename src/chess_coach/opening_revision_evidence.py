"""Read already proved alternative-branch material forks without a solver."""

import time

from .opening_fork_nomination_source import _witness
from .opening_public_proof_read import lookup


def candidate(db, root, learner, decision, move, budget):
    for window in ("initial", "continuation"):
        if time.monotonic() >= budget.expires:
            return None
        proof = lookup(
            db,
            root,
            learner,
            decision["game_id"],
            decision["position_id"],
            move,
            budget.expires,
            fork_window=window,
        )
        if proof is None:
            continue
        witness = _witness(proof, decision["color"], move, branch="alternative")
        if witness:
            return witness
    return None
