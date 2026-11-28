"""Prepare source-bound pin observations under the existing shared deadline."""

import time
from functools import partial

from .opening_public_fork_later import branches
from .opening_public_pin_branch import branch
from .opening_public_prevention_observe import ProofLimit


def evaluate(index, identity, start, deadline):
    budget = {"branch": 0, "total": 0}

    def check():
        if time.monotonic() >= deadline:
            raise TimeoutError("public pin deadline")

    def charge():
        check()
        policy = identity["policy"]["pin"]
        if (
            budget["branch"] >= policy["proofs_per_branch"]
            or budget["total"] >= policy["proofs_per_preparation"]
        ):
            raise ProofLimit()
        budget["branch"] += 1
        budget["total"] += 1

    handler = partial(branch, budget=budget, check=check, charge=charge)
    binding = {**identity, "index_sha256": identity["policy"]["pin"]["index_sha256"]}
    result, sample = branches(index, binding, deadline, brancher=handler)
    for item in result.values():
        item["preparation_proofs"] = budget["total"]
    return result, sample, None
