"""Interrupt a private preview snapshot, including SQLite virtual-machine work."""

import signal
import sqlite3
import time
from contextlib import contextmanager


class PreviewDeadline(BaseException):
    """The preview exceeded its hard process deadline."""


class DeadlineConflict(Exception):
    """The process already owns a deadline timer."""


def _callback_deadline(error, fired):
    # SQLite wraps callback exceptions; only an actual alarm proves expiry.
    return (
        fired
        and getattr(error, "sqlite_errorcode", None) == sqlite3.SQLITE_ERROR
        and str(error) == "user-defined function raised exception"
    )


@contextmanager
def deadline(connection, seconds):
    if seconds <= 0:
        raise PreviewDeadline()
    if any(signal.getitimer(signal.ITIMER_REAL)):
        raise DeadlineConflict("another deadline is active")
    fired = False

    def expired(_signum, _frame):
        nonlocal fired
        fired = True
        raise PreviewDeadline()

    old = signal.signal(signal.SIGALRM, expired)
    until = time.monotonic() + seconds
    signal.setitimer(signal.ITIMER_REAL, seconds)
    connection.set_progress_handler(lambda: int(time.monotonic() >= until), 1000)
    try:
        yield
        if time.monotonic() >= until:
            raise PreviewDeadline()
    except sqlite3.OperationalError as error:
        code = getattr(error, "sqlite_errorcode", None)
        if (code == sqlite3.SQLITE_INTERRUPT and time.monotonic() >= until) or _callback_deadline(
            error, fired
        ):
            raise PreviewDeadline() from None
        raise
    finally:
        connection.set_progress_handler(None, 0)
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
