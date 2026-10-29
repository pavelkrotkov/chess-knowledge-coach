"""Validate a project-local CSV snapshot and serialize import invocations."""

import fcntl
import os
import re
import stat
from contextlib import contextmanager
from pathlib import Path

from .puzzle_csv import _checksum


def snapshot_path(path: str | Path, project_root: str | Path) -> Path:
    root = Path(project_root).resolve(strict=True)
    source = Path(path).resolve(strict=True)
    if not source.is_relative_to(root) or not source.is_file() or source.suffix.lower() != ".csv":
        raise ValueError("decoded CSV must be a regular file inside the project")
    return source


def check_digest(value: str | None) -> None:
    if value is not None and not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("digest must be lowercase SHA-256")


def verify_snapshot(path: Path, digest: str) -> None:
    if _checksum(path) != digest:
        raise ValueError("decoded CSV checksum does not match")


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
