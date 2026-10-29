"""Serialize deep workers independently of pipeline and sync retry locks."""

import fcntl
import os
from contextlib import contextmanager


@contextmanager
def deep_lock(database):
    if str(database) == ":memory:":
        raise ValueError("deep execution requires a file-backed database")
    path = database.resolve().with_suffix(database.suffix + ".deep.lock")
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("deep worker is already running") from None
        yield
    finally:
        os.close(fd)
