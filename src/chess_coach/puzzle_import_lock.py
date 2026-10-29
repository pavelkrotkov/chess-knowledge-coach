"""Serialize independent corpus import workers."""

import fcntl
import os
import stat
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def import_lock(database: Path, project_root: str | Path):
    root = Path(project_root).resolve(strict=True)
    if str(database) == ":memory:":
        raise ValueError("corpus import requires a file-backed database")
    path = database.resolve(strict=True)
    if not path.is_relative_to(root):
        raise ValueError("database must be inside the project")
    lock = path.with_suffix(path.suffix + ".corpus.lock")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("corpus lock is not a regular file")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("corpus importer is already running") from None
        yield
    finally:
        os.close(fd)
