"""Prepare source-bound pin observations under the existing shared deadline."""

import time
from functools import partial

from .opening_public_fork_later import branches
from .opening_public_pin_branch import branch


def evaluate(index, identity, start, deadline):
    budget = {"branch": 0, "total": 0}

    def check():
        if time.monotonic() >= deadline:
            raise TimeoutError("public pin deadline")

    handler = partial(branch, budget=budget, check=check)
    binding = {**identity, "index_sha256": identity["policy"]["pin"]["index_sha256"]}
    result, sample = branches(index, binding, deadline, brancher=handler)
    for item in result.values():
        item["preparation_proofs"] = budget["total"]
    return result, sample, None
