"""Interrupt a private preview snapshot, including SQLite virtual-machine work."""

import signal
import sqlite3
import time
from contextlib import contextmanager


class PreviewDeadline(BaseException):
    """The preview exceeded its hard process deadline."""


class DeadlineConflict(Exception):
    """The process already owns a deadline timer."""


def _expired(_signum, _frame):
    raise PreviewDeadline()


@contextmanager
def deadline(connection, seconds):
    if seconds <= 0:
        raise PreviewDeadline()
    if any(signal.getitimer(signal.ITIMER_REAL)):
        raise DeadlineConflict("another deadline is active")
    old = signal.signal(signal.SIGALRM, _expired)
    until = time.monotonic() + seconds
    signal.setitimer(signal.ITIMER_REAL, seconds)
    connection.set_progress_handler(lambda: int(time.monotonic() >= until), 1000)
    try:
        yield
        if time.monotonic() >= until:
            raise PreviewDeadline()
    except sqlite3.OperationalError as error:
        if (
            getattr(error, "sqlite_errorcode", None) == sqlite3.SQLITE_INTERRUPT
            and time.monotonic() >= until
        ):
            raise PreviewDeadline() from None
        raise
    finally:
        connection.set_progress_handler(None, 0)
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
