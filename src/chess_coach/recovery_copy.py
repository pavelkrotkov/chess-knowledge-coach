"""Copy a pinned SQLite snapshot and compare it before publication."""

import sqlite3
from contextlib import closing
from pathlib import Path

from .recovery_deadline import Deadline
from .recovery_fidelity import verify_fidelity
from .recovery_verify import verify_database


def copy_database(source: Path, temporary: Path) -> None:
    with source.open("rb") as stream:
        if stream.read(16) != b"SQLite format 3" + bytes([0]):
            raise ValueError("source is not a valid SQLite database")
    source_uri = source.as_uri() + "?mode=ro"
    deadline = Deadline()
    with (
        closing(sqlite3.connect(source_uri, uri=True, timeout=5)) as reader,
        closing(sqlite3.connect(temporary, timeout=5)) as writer,
    ):
        reader.set_progress_handler(deadline.progress, 1000)
        writer.set_progress_handler(deadline.progress, 1000)
        reader.execute("BEGIN")
        reader.execute("SELECT count(*) FROM main.sqlite_schema").fetchone()
        deadline.check()
        reader.backup(writer, pages=128, progress=deadline.backup_progress, sleep=0.1)
        if writer.execute("PRAGMA journal_mode=DELETE").fetchone()[0] != "delete":
            raise ValueError("backup could not be made standalone")
        verify_database(writer)
        verify_fidelity(reader, writer, deadline)
        reader.rollback()
