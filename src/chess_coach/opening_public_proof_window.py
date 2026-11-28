"""Choose one fork window and its independent immutable source binding."""

from .opening_public_back_rank_policy import policy as back_rank_policy
from .opening_public_created_backrank_policy import policy as created_backrank_policy
from .opening_public_discovery_material_policy import opportunity as discovery_opportunity_policy
from .opening_public_discovery_material_policy import policy as discovery_material_policy
from .opening_public_double_mate_policy import policy as double_mate_policy
from .opening_public_fork_later import bound as full_bound
from .opening_public_mate_policy import policy as mate_policy
from .opening_public_pin_policy import policy as pin_policy
from .opening_public_prevention_policy import prevention
from .opening_public_proof_evaluate import evaluate as evaluate
from .opening_public_proof_versions import combined, continuation
from .opening_public_protection_policy import protection
from .opening_public_short_mate_policy import policy as short_mate_policy
from .opening_public_skewer_policy import policy as skewer_policy


def choose(base, full, kind, window):
    if kind == "fork":
        return continuation(base, full[1])
    return {
        "prevention": prevention,
        "mate": mate_policy,
        "pin": pin_policy,
        "short_mate": short_mate_policy,
        "back_rank": back_rank_policy,
        "created_backrank": created_backrank_policy,
        "skewer": skewer_policy,
        "double_mate": double_mate_policy,
        "discovery_material": discovery_material_policy,
        "discovery_opportunity": discovery_opportunity_policy,
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
