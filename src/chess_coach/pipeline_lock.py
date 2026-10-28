"""Serialize pipeline invocations using a lock beside the selected database."""

import fcntl
import os
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def pipeline_lock(database: Path):
    if str(database) == ":memory:":
        raise ValueError("pipeline requires a file-backed database")
    lock_path = database.resolve().with_suffix(database.suffix + ".pipeline.lock")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("pipeline is already running") from None
        yield
    finally:
        os.close(fd)
