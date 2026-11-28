"""Execute the selected bounded public proof and branch coverage."""

from .opening_public_back_rank import evaluate as back_rank_evaluate
from .opening_public_created_backrank import evaluate as created_backrank_evaluate
from .opening_public_discovery_material import branch as discovery_material_branch
from .opening_public_double_mate import evaluate as double_mate_evaluate
from .opening_public_fork_later import branches as later_branches
from .opening_public_mate import evaluate as mate_evaluate
from .opening_public_pin import evaluate as pin_evaluate
from .opening_public_prevention import evaluate as prevention_evaluate
from .opening_public_proof_prepare import branches
from .opening_public_short_mate import evaluate as short_mate_evaluate
from .opening_public_skewer import evaluate as skewer_evaluate


def evaluate(index, base, identity, full, start, deadline):
    if {"discovery_material", "discovery_opportunity"} & identity["policy"].keys():
        binding = {**identity, "index_sha256": full[1]}
        result, sample = later_branches(
            full[0], binding, deadline, brancher=discovery_material_branch
        )
        return result, sample, None
    for kind, handler in (
        ("double_mate", double_mate_evaluate),
        ("skewer", skewer_evaluate),
        ("back_rank", back_rank_evaluate),
        ("created_backrank", created_backrank_evaluate),
        ("short_mate", short_mate_evaluate),
        ("mate", mate_evaluate),
        ("pin", pin_evaluate),
        ("prevention", prevention_evaluate),
    ):
        if kind in identity["policy"]:
            return handler(full[0], identity, start, deadline)
    result, sample = branches(index, base if full else identity, start, deadline)
    coverage = None
    if full:
        later, coverage = later_branches(full[0], {**identity, "index_sha256": full[1]}, deadline)
        for label in ("played", "alternative"):
            result[label]["forks"] = later[label]
    return result, sample, coverage
