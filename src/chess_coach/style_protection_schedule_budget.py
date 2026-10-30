"""Bound original-protection resolutions independently of report proof work."""

from contextlib import contextmanager
from contextvars import ContextVar

CURRENT: ContextVar[dict[str, int] | None] = ContextVar(
    "protection_resolution_budget", default=None
)
MAX_RESOLUTIONS = 3


def take():
    budget = CURRENT.get()
    if budget is None or budget["used"] >= budget["limit"]:
        return False
    budget["used"] += 1
    return True


@contextmanager
def resolution_budget():
    budget = {"used": 0, "limit": MAX_RESOLUTIONS}
    token = CURRENT.set(budget)
    try:
        yield budget
    finally:
        CURRENT.reset(token)
