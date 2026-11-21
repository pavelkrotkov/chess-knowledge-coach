"""Require a bounded-error SQLite integrity and foreign-key result."""


def verify(connection):
    result = connection.execute("PRAGMA integrity_check(1)").fetchone()
    if result is None or result[0] != "ok":
        raise ValueError("database integrity unavailable")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("database foreign keys unavailable")
