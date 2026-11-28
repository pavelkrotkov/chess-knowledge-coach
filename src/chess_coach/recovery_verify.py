"""Verify SQLite copies without exposing stored contents."""

import sqlite3
from pathlib import Path


def verify_database(connection: sqlite3.Connection) -> None:
    result = connection.execute("PRAGMA integrity_check").fetchall()
    if result != [("ok",)]:
        raise ValueError("database integrity check failed")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("database foreign key check failed")


def require_standalone(source: Path) -> None:
    with source.open("rb") as stream:
        header = stream.read(20)
    if len(header) < 20 or header[:16] != b"SQLite format 3" + bytes([0]):
        raise ValueError("source is not a valid SQLite database")
    if header[18:20] != bytes([1, 1]):
        raise ValueError("restore requires a standalone backup; run backup-db first")


def verify_standalone(path, deadline):
    from contextlib import closing

    from .recovery_gzip_memory import configure

    require_standalone(path)
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)) as reader:
        reader.set_progress_handler(deadline.progress, 1000)
        reader.execute("PRAGMA query_only=ON")
        configure(reader)
        verify_database(reader)
