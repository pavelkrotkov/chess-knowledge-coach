"""Verify one mate-now answer using a bounded original-history replay."""

from .objective_contract import UNAVAILABLE
from .objective_current import current
from .objective_events import assistance
from .objective_fork_defense_budget import BudgetExceeded
from .objective_fork_defense_contract import OBJECTIVE as FORK_DEFENSE_OBJECTIVE
from .objective_history_dispatch import replay, supported
from .objective_pin_prevent_budget import BudgetExceeded as PinBudgetExceeded
from .objective_pin_prevent_contract import OBJECTIVE as PIN_PREVENT_OBJECTIVE
from .objective_provenance import SECONDS as SECONDS
from .objective_provenance import VERSION as VERSION
from .objective_provenance import provenance as provenance
from .objective_verify_dispatch import verify
from .objective_work_scope import budget_result
from .objective_work_scope import scope as work_scope
from .recurrence_snapshot import read_snapshot


def compute(db, request, clock, *, seconds=SECONDS):
    with work_scope(request):
        if request["objective_version"] in {FORK_DEFENSE_OBJECTIVE, PIN_PREVENT_OBJECTIVE}:
            with read_snapshot(db):
                return _compute(db, request, clock, seconds=seconds)
        return _compute(db, request, clock, seconds=seconds)


def _compute(db, request, clock, *, seconds):
    start = clock()
    base = provenance(request, seconds)
    try:
        session, events = current(db, request)
        base["assistance"] = assistance(events[:-1])
    except (PinBudgetExceeded, BudgetExceeded) as error:
        return budget_result(base, error)
    except (ValueError, KeyError, TypeError, IndexError):
        return {**base, "status": "unresolved", "reason": "source_unavailable"}
    if request["history_mode"] == UNAVAILABLE:
        return {**base, "status": "unresolved", "reason": "history_unavailable"}
    if not supported(request):
        return {**base, "status": "unresolved", "reason": "history_mode_not_supported"}
    try:
        board, move = replay(db, session, events, request)
    except (ValueError, KeyError, TypeError, IndexError):
        return {**base, "status": "unresolved", "reason": "history_unavailable"}
    try:
        return verify(board, move, request, events, clock, start, seconds, base, session)
    except (PinBudgetExceeded, BudgetExceeded) as error:
        return budget_result(base, error)


def unresolved(request, reason):
    return {**provenance(request), "status": "unresolved", "reason": reason}
