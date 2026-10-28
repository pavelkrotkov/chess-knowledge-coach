"""Copy a live SQLite database to a verified private temporary file."""

import sqlite3
import time
from contextlib import closing
from pathlib import Path

from .recovery_verify import verify_database


def copy_database(source: Path, temporary: Path) -> None:
    with source.open("rb") as stream:
        if stream.read(16) != b"SQLite format 3" + bytes([0]):
            raise ValueError("source is not a valid SQLite database")
    source_uri = source.as_uri() + "?mode=ro"
    with (
        closing(sqlite3.connect(source_uri, uri=True, timeout=30)) as reader,
        closing(sqlite3.connect(temporary, timeout=30)) as writer,
    ):
        reader.backup(writer, pages=128, progress=_progress(), sleep=0.1)
        if writer.execute("PRAGMA journal_mode=DELETE").fetchone()[0] != "delete":
            raise ValueError("backup could not be made standalone")
        verify_database(writer)


def _progress():
    deadline = time.monotonic() + 30

    def check(status: int, remaining: int, total: int) -> None:
        nonlocal deadline
        now = time.monotonic()
        if status in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
            if now >= deadline:
                raise TimeoutError("SQLite backup could not acquire a read lock")
        else:
            deadline = now + 30

    return check
