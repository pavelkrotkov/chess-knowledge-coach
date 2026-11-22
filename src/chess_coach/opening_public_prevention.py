"""Prepare one bounded prevention operation against the verified full index."""

import time
from functools import partial

from .opening_public_fork_later import branches
from .opening_public_prevention_branch import branch
from .opening_public_prevention_observe import ProofLimit


def evaluate(index, identity, start, deadline):
    budget = {"proofs": 0, "exhausted": False}
    policy = identity["policy"]["prevention"]

    def check():
        if time.monotonic() >= deadline:
            raise TimeoutError("public prevention deadline")

    def charge():
        check()
        if budget["proofs"] >= policy["proofs_per_preparation"]:
            budget["exhausted"] = True
            raise ProofLimit()
        budget["proofs"] += 1

    handler = partial(branch, start=start, budget=budget, check=check, charge=charge)
    result, sample = branches(index, identity, deadline, brancher=handler)
    for item in result.values():
        item["preparation_proofs"] = budget["proofs"]
    return result, sample, None
