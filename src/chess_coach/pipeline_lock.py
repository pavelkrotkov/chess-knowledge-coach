"""Serialize pipeline invocations using a lock beside the selected database."""

import fcntl
import os
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def pipeline_lock(database: Path, *, sync: bool = False):
    if str(database) == ":memory:":
        raise ValueError("pipeline requires a file-backed database")
    suffix = ".sync.lock" if sync else ".pipeline.lock"
    lock_path = database.resolve().with_suffix(database.suffix + suffix)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | (0 if sync else fcntl.LOCK_NB))
        except BlockingIOError:
            raise RuntimeError("pipeline is already running") from None
        yield
    finally:
        os.close(fd)
