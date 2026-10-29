"""Compare SQLite logical schema, metadata and all supported table values."""

import sqlite3

from .recovery_fidelity_budget import preflight
from .recovery_fidelity_rows import compare_rows
from .recovery_fidelity_schema import schema
from .recovery_fidelity_tables import tables

# Cap each SQLite value and the aggregate estimated result row before fetching.
MAX_RECORD_BYTES = 16 * 1024 * 1024


def verify_fidelity(reader, writer, deadline):
    try:
        _compare(reader, writer, deadline)
    except (sqlite3.Error, UnicodeError, ValueError, TypeError, OverflowError):
        raise ValueError("database logical fidelity verification failed") from None


def _compare(reader, writer, deadline):
    for connection in (reader, writer):
        connection.text_factory = bytes
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_RECORD_BYTES)
    for pragma in ("user_version", "application_id", "encoding"):
        deadline.check()
        if (
            reader.execute("PRAGMA " + pragma).fetchone()
            != writer.execute("PRAGMA " + pragma).fetchone()
        ):
            raise ValueError("database logical fidelity verification failed")
    for name, without_rowid in _tables(reader, writer):
        deadline.check()
        preflight(reader, name, deadline, MAX_RECORD_BYTES)
        preflight(writer, name, deadline, MAX_RECORD_BYTES)
        compare_rows(reader, writer, name, without_rowid, deadline)
    deadline.check()


def _tables(reader, writer):
    source_schema = schema(reader)
    if source_schema != schema(writer):
        raise ValueError("database logical fidelity verification failed")
    left, right = tables(reader), tables(writer)
    expected = {name for kind, name in source_schema if kind == b"table"}
    if sorted(left) != sorted(right) or {row[0] for row in left} != expected:
        raise ValueError("database logical fidelity verification failed")
    return left
