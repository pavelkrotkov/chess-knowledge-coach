"""Sample first-turn opportunities from the pinned time-control index."""

from .opening_fit_later_index import locate
from .opening_fit_reference import sample
from .opening_public_proof_index import index_hash


def opportunities(root, subject, color, path, items, control, budget):
    binding = locate(root, subject)
    index, _, transform = binding
    checksum = index_hash(index, budget.expires)
    public = {}
    for item in items:
        budget.check()
        public[item["uci"]] = sample(
            index,
            item["selection"]["parent"],
            item["uci"],
            color,
            control,
            budget.expires,
            decision_ply=len(path) + 1,
            transform=transform,
        )
    if locate(root, subject) != binding:
        raise ValueError("public opportunity index changed")
    return public, {"sha256": checksum, "transform": transform}
