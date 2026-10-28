"""Interrupt blocking network operations at the total worker deadline."""

import signal
import threading
from contextlib import contextmanager

from .pipeline_network_response import BudgetExceeded


class WorkerContextError(RuntimeError):
    """The synchronous worker does not own a safe process timer."""


def _expired(signum, frame) -> None:
    raise BudgetExceeded("network deadline exceeded")


def validate_worker_context() -> None:
    if threading.current_thread() is not threading.main_thread():
        raise WorkerContextError("network worker requires a dedicated process main thread")
    if any(signal.getitimer(signal.ITIMER_REAL)):
        raise WorkerContextError("network worker cannot replace an active process timer")


@contextmanager
def network_deadline(seconds: float):
    validate_worker_context()
    previous = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, seconds)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
