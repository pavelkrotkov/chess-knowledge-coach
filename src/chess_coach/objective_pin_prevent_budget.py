"""Reserve separate existing-pin and created-pin work before observation."""

from contextlib import contextmanager
from contextvars import ContextVar

from .objective_pin_prevent_limits import (
    ANSWER_CAPTURE_PROBES,
    ANSWER_PROOFS,
    CAPTURE_LIMIT,
    PROOF_LIMIT,
    SOURCE_CAPTURE_PROBES,
    SOURCE_PROOFS,
)

CURRENT: ContextVar[dict[str, int] | None] = ContextVar("owned_pin_prevention_budget", default=None)


@contextmanager
def scope():
    if CURRENT.get() is not None:
        yield
        return
    token = CURRENT.set({"proofs": 0, "captures": 0})
    try:
        yield
    finally:
        CURRENT.reset(token)


class BudgetExceeded(ValueError):
    """The current verification lacks reserved pin work."""


def take_source():
    _take(SOURCE_PROOFS, SOURCE_CAPTURE_PROBES)


def take_answer():
    _take(ANSWER_PROOFS, ANSWER_CAPTURE_PROBES)


def _take(proofs, captures):
    budget = CURRENT.get()
    if budget is None:
        raise BudgetExceeded("pin prevention budget unavailable")
    if budget["proofs"] + proofs > PROOF_LIMIT or budget["captures"] + captures > CAPTURE_LIMIT:
        raise BudgetExceeded("pin prevention budget exhausted")
    budget["proofs"] += proofs
    budget["captures"] += captures
