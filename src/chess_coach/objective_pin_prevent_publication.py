"""Recheck existing prevention results without rewriting their history."""

from .objective_current import current
from .objective_pin_prevent_budget import BudgetExceeded
from .objective_pin_prevent_contract import OBJECTIVE
from .objective_verify import unresolved


def current_existing(db, request, result):
    if request["objective_version"] != OBJECTIVE:
        return result
    try:
        current(db, request)
    except BudgetExceeded:
        return unresolved(request, "pin_proof_budget_exhausted")
    except (ValueError, KeyError, TypeError, IndexError):
        return unresolved(request, "source_unavailable")
    return result
