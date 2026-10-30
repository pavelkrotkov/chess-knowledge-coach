"""Deadline state for one bounded scheduling invocation."""

import time
from contextvars import ContextVar

DEADLINE: ContextVar[float | None] = ContextVar("style_schedule_deadline", default=None)


def reached():
    deadline = DEADLINE.get()
    return deadline is not None and time.monotonic() >= deadline
