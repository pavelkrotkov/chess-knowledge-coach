"""Choose one fork window and its independent immutable source binding."""

from .opening_public_back_rank import evaluate as back_rank_evaluate
from .opening_public_back_rank_policy import policy as back_rank_policy
from .opening_public_fork_later import bound as full_bound
from .opening_public_fork_later import branches as later_branches
from .opening_public_mate import evaluate as mate_evaluate
from .opening_public_mate_policy import policy as mate_policy
from .opening_public_prevention import evaluate as prevention_evaluate
from .opening_public_prevention_policy import prevention
from .opening_public_proof_prepare import branches
from .opening_public_proof_versions import combined, continuation
from .opening_public_protection_policy import protection
from .opening_public_short_mate import evaluate as short_mate_evaluate
from .opening_public_short_mate_policy import policy as short_mate_policy


def choose(base, full, kind, window):
    if kind == "fork":
        return continuation(base, full[1])
    return {
        "prevention": prevention,
        "mate": mate_policy,
        "short_mate": short_mate_policy,
        "back_rank": back_rank_policy,
    }[kind](base, full[1], window)


def select(base, root, subject, deadline, kind, window):
    if kind == "protection":
        return protection(base, window=window), None
    if kind == "capture":
        return base, None
    if kind == "fork" and window == "initial":
        return combined(base), None
    full = full_bound(root, subject, deadline)
    return choose(base, full, kind, window), full


def evaluate(index, base, identity, full, start, deadline):
    for kind, handler in (
        ("back_rank", back_rank_evaluate),
        ("short_mate", short_mate_evaluate),
        ("mate", mate_evaluate),
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
