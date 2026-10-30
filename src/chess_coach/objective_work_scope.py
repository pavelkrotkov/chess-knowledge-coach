"""Select the request's independent bounded verifier work scope."""

from contextlib import nullcontext

from .objective_fork_defense_budget import scope as fork_scope
from .objective_fork_defense_contract import OBJECTIVE as FORK_OBJECTIVE
from .objective_pin_prevent_budget import BudgetExceeded as PinBudgetExceeded
from .objective_pin_prevent_budget import scope as pin_scope
from .objective_pin_prevent_contract import OBJECTIVE as PIN_OBJECTIVE


def scope(request):
    return {
        FORK_OBJECTIVE: fork_scope,
        PIN_OBJECTIVE: pin_scope,
    }.get(request["objective_version"], nullcontext)()


def budget_result(base, error):
    family = "pin" if isinstance(error, PinBudgetExceeded) else "fork"
    return {**base, "status": "unresolved", "reason": family + "_proof_budget_exhausted"}
