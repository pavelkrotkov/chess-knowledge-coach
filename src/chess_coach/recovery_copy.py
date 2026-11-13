"""Copy a pinned SQLite snapshot and compare it before publication."""

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from .recovery_fidelity import verify_fidelity
from .recovery_verify import verify_database


@contextmanager
def pinned(source: Path, deadline):
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=5)) as reader:
        reader.set_progress_handler(deadline.progress, 1000)
        reader.execute("PRAGMA temp_store=MEMORY")
        reader.execute("BEGIN")
        reader.execute("SELECT count(*) FROM main.sqlite_schema").fetchone()
        deadline.check()
        try:
            yield reader
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
