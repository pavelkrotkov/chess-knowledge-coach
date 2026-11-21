"""Share a bounded slide-work budget across source, answer and publication."""

from contextlib import contextmanager
from contextvars import ContextVar

from .objective_pin_prevent_budget import BudgetExceeded
from .objective_pin_prevent_budget import scope as pin_scope

LIMIT = 8192
PIN_REVALIDATION = 256
CURRENT: ContextVar[list[int] | None] = ContextVar("owned_pin_slide_budget", default=None)


@contextmanager
def scope():
    with pin_scope():
        if CURRENT.get() is not None:
            yield
            return
        token = CURRENT.set([0])
        try:
            yield
        finally:
            CURRENT.reset(token)


def take(units):
    state = CURRENT.get()
    if state is None or state[0] + units > LIMIT:
        raise BudgetExceeded("pin slide work limit")
    state[0] += units
