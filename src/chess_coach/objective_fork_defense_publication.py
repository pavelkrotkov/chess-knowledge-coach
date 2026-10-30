"""Recheck existing fork-defense results without rewriting their history."""

from .objective_current import current
from .objective_fork_avoidance_contract import OBJECTIVE as AVOIDANCE_OBJECTIVE
from .objective_fork_defense_budget import BudgetExceeded
from .objective_fork_defense_contract import OBJECTIVE
from .objective_verify import unresolved


def current_existing(db, request, result):
    if request["objective_version"] not in {OBJECTIVE, AVOIDANCE_OBJECTIVE}:
        return result
    try:
        current(db, request)
    except BudgetExceeded:
        return unresolved(request, "fork_proof_budget_exhausted")
    except (ValueError, KeyError, TypeError, IndexError):
        return unresolved(request, "source_unavailable")
    return result
