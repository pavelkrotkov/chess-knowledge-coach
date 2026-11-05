"""Apply the shared node budget and deadline to each short-mate root."""

from .mate_proof import MAX_NODES, _root
from .objective_short_judge import DeadlineBudget


def new_budget(clock, deadline):
    return DeadlineBudget(MAX_NODES, clock, deadline)


def checked_root(board, move, budget):
    if budget.clock() >= budget.deadline:
        return None
    result = _root(board, move, budget)
    return result["status"] if budget.clock() < budget.deadline else None
