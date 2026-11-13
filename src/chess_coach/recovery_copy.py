"""Copy a pinned SQLite snapshot and compare it before publication."""

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from .recovery_deadline import Deadline
from .recovery_fidelity import verify_fidelity
from .recovery_verify import verify_database


@contextmanager
def pinned(source: Path):
    with source.open("rb") as stream:
        header = stream.read(20)
    if len(header) < 20 or header[:16] != b"SQLite format 3" + bytes([0]):
        raise ValueError("source is not a valid SQLite database")
    # Do not let a read-only open create missing WAL sidecars before preflight.
    if 2 in header[18:20] and not all(
        Path(str(source) + suffix).is_file() for suffix in ("-wal", "-shm")
    ):
        raise ValueError("WAL source requires existing WAL and shared-index files")
    deadline = Deadline()
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=5)) as reader:
        reader.set_progress_handler(deadline.progress, 1000)
        reader.execute("PRAGMA temp_store=MEMORY")
        reader.execute("BEGIN")
        reader.execute("SELECT count(*) FROM main.sqlite_schema").fetchone()
        deadline.check()
        try:
            yield reader, deadline
        finally:
            reader.rollback()


def copy_database(reader, temporary: Path, deadline, guard) -> None:
    with closing(sqlite3.connect(temporary, timeout=5)) as writer:
        writer.set_progress_handler(deadline.progress, 1000)
        writer.execute("PRAGMA temp_store=MEMORY")
        reader.backup(writer, pages=128, progress=guard.progress, sleep=0.1)
        if writer.execute("PRAGMA journal_mode=DELETE").fetchone()[0] != "delete":
            raise ValueError("backup could not be made standalone")
        verify_database(writer)
        verify_fidelity(reader, writer, deadline)
