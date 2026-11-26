"""Select the request's independent bounded verifier work scope."""

from contextlib import nullcontext

from .capture_certificate_store import location as capture_location
from .objective_capture_contract import GAIN_OBJECTIVE, TARGET_OBJECTIVE
from .objective_fork_avoidance_contract import OBJECTIVE as AVOIDANCE_OBJECTIVE
from .objective_fork_defense_budget import scope as fork_scope
from .objective_fork_defense_contract import OBJECTIVE as FORK_OBJECTIVE
from .objective_pin_prevent_budget import BudgetExceeded as PinBudgetExceeded
from .objective_pin_prevent_budget import scope as pin_scope
from .objective_pin_prevent_contract import OBJECTIVE as PIN_OBJECTIVE
from .objective_pin_slide_budget import scope as slide_scope
from .objective_pin_slide_contract import OBJECTIVE as SLIDE_OBJECTIVE


def scope(request):
    return {
        FORK_OBJECTIVE: fork_scope,
        AVOIDANCE_OBJECTIVE: fork_scope,
        PIN_OBJECTIVE: pin_scope,
        SLIDE_OBJECTIVE: slide_scope,
    }.get(request["objective_version"], nullcontext)()


def budget_result(base, error):
    family = "pin" if isinstance(error, PinBudgetExceeded) else "fork"
    return {**base, "status": "unresolved", "reason": family + "_proof_budget_exhausted"}


def require_capture_scope(db, rows, subject):
    if (
        any(row["objective_version"] in {TARGET_OBJECTIVE, GAIN_OBJECTIVE} for row in rows)
        and capture_location(db, getattr(db, "capture_root", None), subject) is None
    ):
        raise ValueError("capture verification requires an explicit --project-root")
