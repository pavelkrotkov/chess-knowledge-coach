"""Reserve bounded fork proof work for one queued verification."""

from contextlib import contextmanager
from contextvars import ContextVar

from .fork_defense_anchor import MAX_PROOFS
from .fork_defense_scan import MAX_CANDIDATES

SOURCE_UNITS = max(MAX_CANDIDATES + MAX_PROOFS, 2 * MAX_CANDIDATES)
ANSWER_UNITS = MAX_CANDIDATES
LIMIT = SOURCE_UNITS * 2 + ANSWER_UNITS
CURRENT: ContextVar[dict[str, int] | None] = ContextVar(
    "owned_fork_defense_proof_budget", default=None
)


class BudgetExceeded(ValueError):
    """The current verification lacks reserved proof capacity."""


@contextmanager
def scope():
    if CURRENT.get() is not None:
        yield
        return
    token = CURRENT.set({"reserved": 0, "limit": LIMIT})
    try:
        yield
    finally:
        CURRENT.reset(token)


def reserve(units):
    budget = CURRENT.get()
    if budget is None:
        raise BudgetExceeded("fork proof budget unavailable")
    if budget["reserved"] + units > budget["limit"]:
        raise BudgetExceeded("fork proof budget exhausted")
    budget["reserved"] += units
